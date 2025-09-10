"""Temporal detector implementation (combined variance/attention/TFT-lite paths).

This consolidates previous stub and advanced scaffold into a single, clean
implementation supporting the encoder modes referenced by tests:
  - variance
  - attn
  - tft (lite deterministic model)

Registration is idempotent via ``register_temporal``. Feature flags:
  - detection.temporal.simple_model must be True for any processing.
  - detection.temporal.encoder selects encoder (variance | attn | tft).
  - detection.temporal.enable_transformer can be used as higher-level gate (pipeline side).
"""
from __future__ import annotations

from core.event import Event
from config import runtime_params
from core.sequence.buffer import buffers as vector_buffers
from core.features.registry import feature_order, to_vector
from core import metrics
import math, time
from core.retrieval.corpus import corpus
from core.temporal.calibration import calibrator
try:
    from core.temporal.models.tft_lite import TFTLite
except Exception:  # pragma: no cover
    TFTLite = None  # type: ignore


class TemporalDetector:
    name = "temporal"

    def __init__(self):
        self._events = 0
        self._last_latency = 0.0
        self._guard_tripped = 0
        self._last_save_time = 0.0
        self._updates_since_save = 0
        # Rolling variance tracker per tenant: (mean, m2, count) Welford style with decay
        self._res_stats: dict[str, dict[str, float]] = {}

    def process(self, ev: Event):  # noqa: D401
        """Consume event and return empty anomaly list (stub)."""
        self._events += 1
        anomalies = []
        # Acquire feature order once per call for downstream labeling
        try:
            order = feature_order()
        except Exception:
            order = []
        # Encoder selection: variance | attn | tft
        try:
            # Only proceed if simple temporal model explicitly enabled; transformer enable flag alone keeps stub silent
            if bool(runtime_params.get_param("detection.temporal.simple_model")):
                order = feature_order()
                try:
                    win = int(runtime_params.get_param("snn.encoding_window") or 20)
                except Exception:
                    win = 20
                mgr = vector_buffers(window=win, feature_order=order)
                vec = to_vector({k: v for k, v in ev.features.items() if isinstance(v, (int, float))})
                buf = mgr.get(ev.tenant_id)
                # Memory/backpressure guard: enforce max window * tenants approximate bound
                try:
                    max_window = int(runtime_params.get_param("temporal.guard.max_window") or 2000)
                except Exception:
                    max_window = 2000
                # Rough guard: if internal deque length about to exceed max_window (shouldn't due to maxlen) skip + trip metric
                try:
                    if len(buf.window_view()) >= max_window:
                        metrics.TEMPORAL_GUARD_TRIPS_TOTAL.labels(tenant=ev.tenant_id, reason="memory").inc()  # type: ignore[attr-defined]
                    else:
                        buf.add_vector(vec)
                except Exception:
                    pass
                if buf.ready():
                    window_view = buf.window_view()
                    dims = len(window_view[0]) if window_view else 0
                    if dims and window_view:
                        encoder_sel = str(runtime_params.get_param("detection.temporal.encoder") or "variance")
                        mean_var = 0.0
                        attn_score = 0.0
                        residual_norm = 0.0
                        residual_vector = []
                        pred_vec = []
                        if encoder_sel == "variance":
                            var_sum = 0.0
                            for j in range(dims):
                                col = [row[j] for row in window_view]
                                m = sum(col)/len(col)
                                var = sum((x-m)**2 for x in col)/max(1,len(col)-1)
                                var_sum += var
                            mean_var = var_sum / max(1,dims)
                            try:
                                metrics.TEMPORAL_VARIANCE_MEAN.labels(tenant=ev.tenant_id).set(mean_var)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            thr = float(runtime_params.get_param("detection.temporal.var_threshold") or 0.18)
                            fire = mean_var >= thr
                            score = math.tanh(mean_var * 3.0) if fire else 0.0
                            reason = "temporal_variance_spike"
                        elif encoder_sel == "attn":
                            # Lightweight attention: per-dim attention weight ~ latest value emphasis
                            latest = window_view[-1]
                            # compute simple similarity of each step to latest (cosine over normalized space ~ dot since [0,1])
                            sims = []
                            for row in window_view:
                                dot = sum(a*b for a,b in zip(row, latest))
                                sims.append(dot)
                            # softmax
                            max_s = max(sims) if sims else 0.0
                            exp = [math.exp(s-max_s) for s in sims]
                            Z = sum(exp) or 1.0
                            weights = [e/Z for e in exp]
                            # weighted deviation relative to mean vector
                            mean_vec = [sum(row[j] for row in window_view)/len(window_view) for j in range(dims)]
                            attn_dev = 0.0
                            for w,row in zip(weights, window_view):
                                attn_dev += w * sum(abs(a-b) for a,b in zip(row, mean_vec))/max(1,dims)
                            attn_score = math.tanh(attn_dev * 2.5)
                            thr = float(runtime_params.get_param("detection.temporal.attn_threshold") or 0.22)
                            fire = attn_score >= thr
                            score = attn_score if fire else 0.0
                            reason = "temporal_attn_deviation"
                            try:
                                metrics.TEMPORAL_ATTENTION_SCORE.labels(tenant=ev.tenant_id).set(attn_score)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                        elif encoder_sel == "tft" and TFTLite is not None:
                            model = TFTLite(window=win, feature_dim=dims)
                            pred_vec, residual_vector = model.forward(window_view)
                            residual_norm = math.sqrt(sum(r*r for r in residual_vector))
                            mean_var = sum(abs(r) for r in residual_vector)/max(1,dims)
                            score = math.tanh(residual_norm)
                            # Fire if residual norm beyond dynamic median (p50) after calibration priming
                            cal = calibrator()
                            cal.add(ev.tenant_id, residual_norm)
                            p50, p90, p99 = cal.quantiles(ev.tenant_id)
                            fire = residual_norm >= p90 if p90 > 0 else False
                            reason = "temporal_tft_residual_spike" if fire else "temporal_tft_observation"
                            try:
                                metrics.TEMPORAL_RESIDUAL_NORM.labels(tenant=ev.tenant_id).set(residual_norm)  # type: ignore[attr-defined]
                                # Expose calibrated p95 (p90 approximated; future refinement) using p90 as proxy until enough samples for p99 stability
                                if p90 > 0:
                                    metrics.TEMPORAL_RESIDUAL_P95.labels(tenant=ev.tenant_id).set(p90)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                        else:
                            fire = False
                            score = 0.0
                            reason = "temporal_encoder_unknown"
                        if fire:
                            ctx = []
                            try:
                                c = corpus()
                                # Build semantic hint query from top contributing feature (largest latest value)
                                top_idx = 0
                                if window_view:
                                    latest_vec = window_view[-1]
                                    if latest_vec:
                                        top_idx = max(range(len(latest_vec)), key=lambda i: latest_vec[i])
                                feat_name = order[top_idx] if 0 <= top_idx < len(order) else "feature"
                                q = f"temporal {reason} {feat_name}"[:120]
                                # adapt corpus query signature - new query(term, top_k)
                                if hasattr(c, 'query'):
                                    try:
                                        ctx = c.query(q, top_k=3)  # type: ignore[arg-type]
                                    except TypeError:
                                        ctx = c.query(top_k=3)
                            except Exception:
                                ctx = []
                            # Confidence band (calibration over residual_norm or selected score proxy)
                            cal = calibrator()
                            proxy_val = residual_norm or mean_var or attn_score or score
                            if proxy_val > 0:
                                cal.add(ev.tenant_id, proxy_val)
                            band = cal.confidence_band(ev.tenant_id, proxy_val)
                            # Normalized residual (quantile scaling) for fusion contribution path
                            norm_contrib = 0.0
                            try:
                                p50, p90, p99 = cal.quantiles(ev.tenant_id)
                                min_samples = int(runtime_params.get_param("temporal.calibration.min_samples") or 50)
                                # Determine available sample count indirectly via age & stats presence
                                # (Calibrator doesn't expose count directly; infer from sample deque length by private access best-effort)
                                sample_count = 0
                                try:
                                    if hasattr(cal, '_samples'):
                                        dq = cal._samples.get(ev.tenant_id)  # type: ignore[attr-defined]
                                        if dq:
                                            sample_count = len(dq)
                                except Exception:
                                    sample_count = 0
                                if sample_count >= min_samples and p90 > p50:
                                    # Scale using mid-upper band to reduce p99 instability; clip 0..1
                                    denom = (p90 - p50) or 1e-6
                                    norm_contrib = max(0.0, min(1.0, (proxy_val - p50) / denom))
                                    try:
                                        metrics.TEMPORAL_CALIBRATION_CACHE_HITS.labels(tenant=ev.tenant_id).inc()  # type: ignore[attr-defined]
                                    except Exception:
                                        pass
                                else:
                                    # Miss path
                                    norm_contrib = 0.0
                                    try:
                                        metrics.TEMPORAL_CALIBRATION_CACHE_MISSES.labels(tenant=ev.tenant_id).inc()  # type: ignore[attr-defined]
                                    except Exception:
                                        pass
                            except Exception:
                                norm_contrib = 0.0
                            # Update residual variance stats (decayed Welford)
                            if proxy_val > 0:
                                st = self._res_stats.setdefault(ev.tenant_id, {"mean": 0.0, "m2": 0.0, "n": 0.0})
                                # Exponential decay factor
                                alpha = 0.05
                                prev_mean = st["mean"]
                                new_mean = (1 - alpha) * prev_mean + alpha * proxy_val
                                st["mean"] = new_mean
                                # Approx variance update (EW): var_new = (1-alpha)*(var + alpha*(x-prev_mean)^2)
                                diff = proxy_val - prev_mean
                                var_prev = st.get("var", 0.0)
                                var_new = (1 - alpha) * (var_prev + alpha * diff * diff)
                                st["var"] = var_new
                                try:
                                    metrics.TEMPORAL_RESIDUAL_VARIANCE.labels(tenant=ev.tenant_id).set(var_new)  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                                # Guard checks
                                try:
                                    max_var = float(runtime_params.get_param("temporal.guard.max_residual_var") or 5.0)
                                except Exception:
                                    max_var = 5.0
                                if var_new > max_var:
                                    try:
                                        metrics.TEMPORAL_GUARD_TRIPS_TOTAL.labels(tenant=ev.tenant_id, reason="variance").inc()  # type: ignore[attr-defined]
                                    except Exception:
                                        pass
                            try:
                                # Update residual p95 gauge opportunistically when enough samples -> reuse p90 as approximation if p99 not stable yet
                                p50, p90, p99 = cal.quantiles(ev.tenant_id)
                                if p90 > 0:
                                    metrics.TEMPORAL_RESIDUAL_P95.labels(tenant=ev.tenant_id).set(p90)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            try:
                                metrics.TEMPORAL_RESIDUAL_NORM.labels(tenant=ev.tenant_id).set(proxy_val)  # type: ignore[attr-defined]
                                metrics.TEMPORAL_CONFIDENCE_BAND.labels(tenant=ev.tenant_id, band=band).inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            anomalies.append({
                                "detector": self.name,
                                "tenant": ev.tenant_id,
                                "event_id": ev.event_id,
                                "trace_id": ev.trace_id,
                                "reason": reason,
                                "mean_var": mean_var,
                                "score": score,
                                "context": ctx,
                                "confidence_band": band,
                                "residual_norm": residual_norm,
                                "encoder": encoder_sel,
                                "top_residual_features": self._top_residual_features(residual_vector, order) if residual_vector else None,
                                "normalized_residual": norm_contrib,
                            })
                            try:
                                metrics.TEMPORAL_ONLY_ANOMALIES_TOTAL.labels(tenant=ev.tenant_id).inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
        except Exception:
            pass
        # Calibration freshness guard + persistence save cadence (outside try for reliability)
        try:
            cal = calibrator()
            # Load once early (idempotent)
            cal.load(max_age_s=float(runtime_params.get_param("temporal.calibration.max_age_s") or 7200.0))
            # Periodic save
            self._updates_since_save += 1
            now = math.floor(time.time())
            save_interval_updates = int(runtime_params.get_param("temporal.calibration.save_interval_updates") or 200)
            save_interval_s = float(runtime_params.get_param("temporal.calibration.save_interval_s") or 120.0)
            if (self._updates_since_save >= save_interval_updates) or (now - self._last_save_time >= save_interval_s):
                cal.save()
                self._updates_since_save = 0
                self._last_save_time = now
            # Freshness guard per tenant (approx: evaluate only for tenants in stats map)
            try:
                max_stale = float(runtime_params.get_param("temporal.guard.max_calibration_stale_s") or 900.0)
            except Exception:
                max_stale = 900.0
            for tenant in list(self._res_stats.keys()):
                age = cal.last_update_age(tenant)
                try:
                    metrics.TEMPORAL_CALIBRATION_FRESHNESS_S.labels(tenant=tenant).set(age)  # type: ignore[attr-defined]
                except Exception:
                    pass
                if age > max_stale:
                    try:
                        metrics.TEMPORAL_GUARD_TRIPS_TOTAL.labels(tenant=tenant, reason="freshness").inc()  # type: ignore[attr-defined]
                    except Exception:
                        pass
        except Exception:
            pass
        return anomalies

    def _top_residual_features(self, residual_vector, order, k: int = 3):
        try:
            pairs = list(enumerate(residual_vector))
            # rank by abs residual desc
            pairs.sort(key=lambda x: abs(x[1]), reverse=True)
            top = []
            for idx, val in pairs[:k]:
                name = order[idx] if 0 <= idx < len(order) else f"f{idx}"
                top.append({"feature": name, "residual": val})
            return top
        except Exception:
            return None


_TEMPORAL_DETECTOR: TemporalDetector | None = None


def register_temporal():
    global _TEMPORAL_DETECTOR
    if _TEMPORAL_DETECTOR is None:
        _TEMPORAL_DETECTOR = TemporalDetector()
        from core.detect.interface import registry
        registry.register(_TEMPORAL_DETECTOR)
    return _TEMPORAL_DETECTOR


__all__ = ["register_temporal", "TemporalDetector"]
