"""Fusion arbitrator scaffold (Phase 4).

Provides a pluggable strategy interface for combining detector anomaly results.
Initial strategies:
  - pass_through: return per-detector results unchanged (no suppression)
  - baseline_priority: prefer baseline anomalies; include SNN anomalies only if no baseline anomaly for event

Future placeholders (not yet implemented):
  - snn_priority
  - consensus_only (only anomalies present in both)

Arbitrator operates on a mapping detector_name -> List[DetectionResult].
Returns fused list of DetectionResult plus optional metadata.
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Deque
from collections import deque
from .interface import DetectionResult
try:  # Batch 5 enrichment modules
    from core.detect.mitre_enrichment import enrich_with_mitre  # type: ignore
    from core.detect.intel_enrichment import enrich_with_intel  # type: ignore
except Exception:  # pragma: no cover
    def enrich_with_mitre(anoms):
        return anoms
    def enrich_with_intel(anoms):
        return anoms
from core import metrics
from config import runtime_params
try:
    from core.integrations.base import export_all  # type: ignore
    from core.integrations.audit import append_export_audit  # type: ignore
    from core import metrics as _mexp
except Exception:  # pragma: no cover
    def export_all(records, audit_callback=None, metrics_callback=None):  # type: ignore
        return []
    def append_export_audit(name, result):  # type: ignore
        return None
    _mexp = None

class FusionArbitrator:
    def __init__(self):
        self.strategy = (runtime_params.get_param("detection.fusion.strategy") or "pass_through").strip()
        # Ring buffer of suppressed SNN anomalies (store minimal fields)
        self._suppressed: Deque[DetectionResult] = deque(maxlen=500)
        # Temporal tuner state
        self._tuner_last_ts: float = 0.0
        self._tuner_window: Deque[tuple[int,int]] = deque(maxlen=200)  # (baseline_count, temporal_applied) per fuse call
        # Temporal latency tracking (rolling p99 estimation using simple high-water decay)
        self._temporal_lat_samples: Deque[float] = deque(maxlen=500)
        self._temporal_pause_state: dict[str, float] = {}  # tenant -> resume_after_ts (if paused)


    def refresh(self):
        self.strategy = (runtime_params.get_param("detection.fusion.strategy") or self.strategy).strip()

    def fuse(self, detector_results: Dict[str, List[DetectionResult]]) -> Tuple[List[DetectionResult], dict]:
        self.refresh()
        if self.strategy == "baseline_priority":
            res, meta = self._baseline_priority(detector_results)
        elif self.strategy == "consensus_only":
            res, meta = self._consensus_only(detector_results)
        elif self.strategy == "weighted_sum":
            res, meta = self._weighted_sum(detector_results)
        else:
            res, meta = self._pass_through(detector_results)
        # Enrichment chain (idempotent & best-effort)
        try:
            res = enrich_with_mitre(res)
        except Exception:
            pass
        try:
            res = enrich_with_intel(res)
        except Exception:
            pass
        # Integration export hook (best-effort, non-blocking)
        try:
            if res:
                def _metrics_cb(name, result):
                    if _mexp:
                        try:
                            lat = float(result.get("latency_s") or 0.0)
                            _mexp.record_integration_export_metrics(name, result.get("outcome", "unknown"), lat)  # type: ignore
                        except Exception:
                            pass
                export_all(res, audit_callback=append_export_audit, metrics_callback=_metrics_cb)
        except Exception:
            pass
        # Risk overlay removed from fusion (migrated to pipeline async enrichment stage)
        return res, meta

    def _pass_through(self, detector_results: Dict[str, List[DetectionResult]]) -> Tuple[List[DetectionResult], dict]:
        fused: List[DetectionResult] = []
        for results in detector_results.values():
            fused.extend(results)
        return fused, {"strategy": "pass_through", "suppressed": 0}

    def _baseline_priority(self, detector_results: Dict[str, List[DetectionResult]]) -> Tuple[List[DetectionResult], dict]:
        baseline = detector_results.get("baseline") or []
        snn = detector_results.get("snn") or []
        if baseline:
            suppressed = len(snn)
            for r in snn:
                try:
                    self._suppressed.append(r)
                    metrics.FUSION_SUPPRESSED_TOTAL.labels(tenant=r.get("tenant", "unknown"), strategy="baseline_priority", detector="snn").inc()  # type: ignore[attr-defined]
                except Exception:
                    pass
            return list(baseline), {"strategy": "baseline_priority", "suppressed": suppressed}
        fused = list(snn)
        return fused, {"strategy": "baseline_priority", "suppressed": 0}

    def _consensus_only(self, detector_results: Dict[str, List[DetectionResult]]) -> Tuple[List[DetectionResult], dict]:
        """Return only anomalies that appear in both baseline and snn detectors.

        Consensus condition (simplified Phase 4): event-level consensus -> if both produced any anomaly, return union;
        else return empty set (suppress unique sources).
        All anomalies from a single-source event are suppressed.
        """
        baseline = detector_results.get("baseline") or []
        snn = detector_results.get("snn") or []
        if baseline and snn:
            fused = list(baseline) + list(snn)
            return fused, {"strategy": "consensus_only", "suppressed": 0}
        suppressed = 0
        # Suppress whichever side produced anomalies alone
        for rec in baseline:
            try:
                self._suppressed.append(rec)
                suppressed += 1
                metrics.FUSION_SUPPRESSED_TOTAL.labels(tenant=rec.get("tenant", "unknown"), strategy="consensus_only", detector="baseline").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
        for rec in snn:
            try:
                self._suppressed.append(rec)
                suppressed += 1
                metrics.FUSION_SUPPRESSED_TOTAL.labels(tenant=rec.get("tenant", "unknown"), strategy="consensus_only", detector="snn").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
        return [], {"strategy": "consensus_only", "suppressed": suppressed}

    def recent_suppressed(self, limit: int = 50) -> List[DetectionResult]:
        return list(list(self._suppressed)[-limit:])

    def _weighted_sum(self, detector_results: Dict[str, List[DetectionResult]]) -> Tuple[List[DetectionResult], dict]:
        """Experimental weighted sum fusion.

        decision_score = w_b * baseline_indicator + w_s * snn_norm
        snn_norm = clip((activity - threshold) / (threshold*2), 0, 1)
        Emits union; no suppression in first iteration (suppression gate TBD).

        Temporal integration (Phase 4+): Temporal anomalies contribute additive influence: composite += w_t * temporal_norm.
        Influence gated by confidence band (HIGH/CRITICAL) and precision proxy guard. Adaptive tuner periodically
        adjusts runtime param 'detection.temporal.weight' toward target uplift ratio defined by
        fusion.temporal.tuner.target_uplift. Metrics exposed: FUSION_TEMPORAL_WEIGHT, FUSION_TEMPORAL_CONTRIBUTION.
        """
        baseline = detector_results.get("baseline") or []
        snn = detector_results.get("snn") or []
        iforest = detector_results.get("iforest") or []
        temporal = detector_results.get("temporal") or []
        hopfield = detector_results.get("hopfield") or []
        # Memory signal weight (Phase3): applied as multiplicative gating factor on temporal contribution
        try:
            # Seed fallback for memory weight
            if runtime_params.get_param("fusion.weight.memory_signal") is None:
                seed = runtime_params.get_param("fusion.memory.signal.seed")
                if seed is not None:
                    try:
                        runtime_params.set_param("fusion.weight.memory_signal", float(seed), reason="seed_memory_weight")  # type: ignore[attr-defined]
                    except Exception:
                        pass
            w_mem = float(runtime_params.get_param("fusion.weight.memory_signal") or 0.0)
            # Clamp to sane max
            if w_mem > 1.0:
                w_mem = 1.0
        except Exception:
            w_mem = 0.0
        fused: List[DetectionResult] = []
        try:
            w_b = float(runtime_params.get_param("fusion.weight.baseline") or 0.6)
            w_s = float(runtime_params.get_param("fusion.weight.snn") or 0.4)
            w_if = float(runtime_params.get_param("fusion.weight.iforest") or 0.0)
            # New optional temporal transformer contribution weight
            w_tr = float(runtime_params.get_param("fusion.weight.transformer") or 0.0)
            suppress_thr = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)
            # Temporal adaptive weight (gated by confidence band)
            w_t = float(runtime_params.get_param("detection.temporal.weight") or 0.0)
            temporal_precision_max = float(runtime_params.get_param("fusion.temporal.precision_max_rate") or 1.0)
            # Feature flag gating
            temporal_enabled = runtime_params.get_param("detection.temporal.enabled")
            if temporal_enabled in {0, False, "0", "false"}:
                w_t = 0.0
            transformer_enabled = runtime_params.get_param("detection.transformer.enabled")
            if transformer_enabled in {0, False, "0", "false"}:
                w_tr = 0.0
        except Exception:
            w_b, w_s, w_if, w_tr, suppress_thr, w_t, temporal_precision_max = 0.6, 0.4, 0.0, 0.0, 0.0, 0.0, 1.0
        if (w_b + w_s) <= 1e-9:
            w_b, w_s = 0.5, 0.5
        # Transformer deviation (single global contribution per fuse call) - scaffold
        transformer_dev = 0.0
        if w_tr > 0:
            try:
                from core.temporal.transformer import instance as tt_instance  # type: ignore
                transformer_dev = float(tt_instance().deviation())
            except Exception:
                transformer_dev = 0.0
        # We do NOT renormalize with temporal weight to preserve explicit influence scaling; temporal is additive.
        # Baseline anomalies
        for r in baseline:
            r2 = dict(r)
            base_score = (w_b * 1.0) + (w_tr * transformer_dev)
            r2["fusion_decision_score"] = base_score
            r2["fusion_components"] = {"baseline": 1.0, "snn_norm": 0.0, "iforest_norm": 0.0, "temporal": 0.0, "transformer": transformer_dev, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr}}
            fused.append(r2)  # type: ignore[arg-type]
        # SNN anomalies
        baseline_present = 1.0 if baseline else 0.0
        suppressed = 0
        for r in snn:
            r2 = dict(r)
            thresh = float(r.get("threshold") or 1.0)
            activity = float(r.get("activity") or 0.0)
            snn_norm = self._norm_snn(activity, thresh)
            score = (w_b * baseline_present) + (w_s * snn_norm) + (w_tr * transformer_dev)
            r2["fusion_decision_score"] = score
            r2["fusion_components"] = {"baseline": baseline_present, "snn_norm": snn_norm, "iforest_norm": 0.0, "temporal": 0.0, "transformer": transformer_dev, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr}}
            # Suppress SNN-only anomalies under threshold (baseline_present==0)
            if baseline_present == 0 and suppress_thr > 0 and score < suppress_thr:
                suppressed += 1
                try:
                    self._suppressed.append(r2)
                    metrics.FUSION_SUPPRESSED_TOTAL.labels(tenant=r2.get("tenant", "unknown"), strategy="weighted_sum", detector="snn").inc()  # type: ignore[attr-defined]
                except Exception:
                    pass
                continue
            fused.append(r2)  # type: ignore[arg-type]
        # Isolation Forest anomalies
        for r in iforest:
            r2 = dict(r)
            if_norm = max(0.0, min(1.0, float(r2.get("score") or 0.0)))
            score = (w_b * baseline_present) + (w_s * 0.0) + (w_if * if_norm) + (w_tr * transformer_dev)
            r2["fusion_decision_score"] = score
            r2["fusion_components"] = {"baseline": baseline_present, "snn_norm": 0.0, "iforest_norm": if_norm, "temporal": 0.0, "transformer": transformer_dev, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr}}
            fused.append(r2)
        # Temporal anomalies (apply only if weight >0 and confidence band HIGH/CRITICAL)
        temporal_applied = 0
        for r in temporal:
            r2 = dict(r)
            band = str(r2.get("confidence_band") or "LOW").upper()
            # Pause guard: if temporal path paused for tenant skip contribution
            tenant_id = r2.get("tenant", "unknown")
            now_ts = None
            paused = False
            try:
                import time as _t
                now_ts = _t.time()
                resume_after = self._temporal_pause_state.get(tenant_id, 0.0)
                if resume_after and now_ts < resume_after:
                    paused = True
                elif resume_after and now_ts >= resume_after:
                    # auto-resume
                    try:
                        metrics.TEMPORAL_PAUSE_STATE.labels(tenant=tenant_id).set(0)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    self._temporal_pause_state.pop(tenant_id, None)
            except Exception:
                paused = False
            # Precision proxy gating (if precision proxy rate for temporal > allowed, gate). We reuse baseline proxy gauge placeholder by detector label 'temporal' if emitted in future; fallback 0.
            precision_rate = 0.0
            try:
                # Attempt to read internal stored gauge value (Prometheus client stores _value) - best effort
                g = metrics.PRECISION_PROXY_RATE.labels(tenant=r2.get("tenant", "unknown"), detector="temporal")  # type: ignore[attr-defined]
                if hasattr(g, "_value"):
                    precision_rate = float(getattr(g._value, 'get', lambda: 0.0)())  # type: ignore
            except Exception:
                precision_rate = 0.0
            if paused or w_t <= 0 or band not in {"HIGH", "CRITICAL"} or precision_rate > temporal_precision_max:
                # treat as suppressed for weighting (but still pass-through anomaly record for visibility)
                gated_base = (w_b * baseline_present) + (w_tr * transformer_dev)
                r2["fusion_decision_score"] = gated_base
                r2["fusion_components"] = {"baseline": baseline_present, "snn_norm": 0.0, "iforest_norm": 0.0, "temporal": 0.0, "transformer": transformer_dev, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr}, "temporal_gated": True}
                fused.append(r2)  # no suppression metric (anomaly still surfaced; just zero influence)
                continue
            # Normalize temporal score into 0..1 contribution (tanh already ~0..1). Clamp for safety.
            # Prefer calibrated normalized residual if available
            raw_norm = r2.get("normalized_residual")
            if raw_norm is not None:
                temporal_norm = max(0.0, min(1.0, float(raw_norm)))
            else:
                raw = float(r2.get("score") or 0.0)
                temporal_norm = max(0.0, min(1.0, raw))
            # Apply memory gating: effective temporal weight = w_t * (1 + w_mem) if anomaly memory-confirmed later we can revisit scaling.
            # Optional uplift gating: if memory_verified_ratio below fusion.memory.uplift.threshold keep memory multiplier at 0
            uplift_thr = 0.05
            try:
                thr_param = runtime_params.get_param("fusion.memory.uplift.threshold")
                if isinstance(thr_param, (int,float)):
                    uplift_thr = float(thr_param)
            except Exception:
                pass
            mem_ratio_current = 0.0
            try:
                child_map = getattr(metrics.FUSION_MEMORY_VERIFIED_RATIO, '_metrics', {})  # type: ignore[attr-defined]
                for _k, child in child_map.items():
                    try:
                        mem_ratio_current = float(child._value.get())  # type: ignore
                        break
                    except Exception:
                        continue
            except Exception:
                mem_ratio_current = 0.0
            mem_multiplier = (1.0 + max(0.0, w_mem)) if mem_ratio_current >= uplift_thr else 1.0
            effective_w_t = w_t * mem_multiplier
            composite = (w_b * baseline_present) + (w_s * 0.0) + (w_if * 0.0) + (effective_w_t * temporal_norm) + (w_tr * transformer_dev)
            r2["fusion_decision_score"] = composite
            r2["fusion_components"] = {"baseline": baseline_present, "snn_norm": 0.0, "iforest_norm": 0.0, "temporal": temporal_norm, "transformer": transformer_dev, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr, "w_mem": w_mem}, "temporal_gated": False}
            temporal_applied += 1
            try:
                metrics.FUSION_WEIGHT_UPDATES_TOTAL.labels(strategy="temporal_weighted_sum").inc()  # reuse existing counter for now
                metrics.FUSION_TEMPORAL_WEIGHT.labels(tenant=r2.get("tenant", "unknown")).set(w_t)  # type: ignore[attr-defined]
                metrics.FUSION_TEMPORAL_CONTRIBUTION.labels(tenant=r2.get("tenant", "unknown")).set(temporal_norm)  # type: ignore[attr-defined]
            except Exception:
                pass
            fused.append(r2)  # type: ignore[arg-type]
        # Invoke tuner (non-blocking best-effort) with baseline anomaly count and temporal applied count
        try:
            self._maybe_tune_temporal_weight(len(baseline), temporal_applied)
        except Exception:
            pass
        # Export transformer metrics best-effort (use first tenant present among anomalies or 'unknown')
        # Hopfield anomalies (added last; weight handled via dedicated fusion.weight.hopfield if introduced later)
        hopfield_only = 0
        union_ids = set()
        try:
            for r in (baseline + snn + iforest + temporal):
                eid = r.get("event_id") or r.get("ts") or id(r)
                union_ids.add(eid)
        except Exception:
            pass
        for r in hopfield:
            r2 = dict(r)
            eid = r2.get("event_id") or r2.get("ts") or id(r2)
            baseline_present = 1.0 if baseline else 0.0
            score = (w_b * baseline_present) + (w_tr * transformer_dev)  # no dedicated weight yet
            r2["fusion_decision_score"] = score
            r2["fusion_components"] = {"baseline": baseline_present, "snn_norm": 0.0, "iforest_norm": 0.0, "temporal": 0.0, "transformer": transformer_dev, "hopfield": 1.0, "weights": {"w_b": w_b, "w_s": w_s, "w_if": w_if, "w_t": w_t, "w_tr": w_tr}}
            # Track if unique (no prior detectors fired for this event id heuristic)
            unique_flag = False
            if eid not in union_ids:
                unique_flag = True
                hopfield_only += 1
                union_ids.add(eid)
            r2["hopfield_unique"] = unique_flag
            fused.append(r2)  # type: ignore[arg-type]
        # Hopfield unique ratio export
        try:
            total_union = len(union_ids) or 1
            ratio = hopfield_only / total_union
            # Determine tenant: prefer first hopfield anomaly else fallback to any prior anomaly
            tenant_candidate = None
            for r in (hopfield + baseline + snn + iforest + temporal):
                tenant_candidate = r.get("tenant")
                if tenant_candidate:
                    break
            if tenant_candidate is None:
                tenant_candidate = "unknown"
            metrics.HOPFIELD_UNIQUE_RATIO.labels(tenant=tenant_candidate).set(ratio)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            tenant_id = None
            for r in (baseline + snn + iforest + temporal + hopfield):
                tenant_id = r.get("tenant")
                if tenant_id:
                    break
            if tenant_id is None:
                tenant_id = "unknown"
            if w_tr > 0:
                metrics.FUSION_TRANSFORMER_WEIGHT.labels(tenant=tenant_id).set(w_tr)  # type: ignore[attr-defined]
                metrics.FUSION_TRANSFORMER_DEVIATION.labels(tenant=tenant_id).set(transformer_dev)  # type: ignore[attr-defined]
        except Exception:
            pass
        return fused, {"strategy": "weighted_sum", "suppressed": suppressed, "temporal_applied": temporal_applied, "transformer_dev": transformer_dev, "w_tr": w_tr}

    def _maybe_tune_temporal_weight(self, baseline_count: int, temporal_applied: int):
        # Adaptive temporal weight tuner adjusting runtime param 'detection.temporal.weight'.
        # Uplift ratio = temporal_applied / baseline_count (baseline_count>0). Adjusts weight toward target
        # if outside tolerance band and cooldown elapsed. Audited via runtime_params.update_param.
        try:
            if not bool(runtime_params.get_param("fusion.temporal.tuner.enabled")):
                return
            import time, math
            now = time.time()
            cooldown = float(runtime_params.get_param("fusion.temporal.tuner.cooldown_s") or 30.0)
            if (now - self._tuner_last_ts) < cooldown:
                return
            prev_ts = self._tuner_last_ts
            self._tuner_last_ts = now
            # Record window sample
            self._tuner_window.append((baseline_count, temporal_applied))
            try:
                metrics.FUSION_TEMPORAL_TUNER_WINDOW_SIZE.set(len(self._tuner_window))  # type: ignore[attr-defined]
                if prev_ts > 0:
                    metrics.FUSION_TEMPORAL_TUNER_CYCLE_SECONDS.observe(now - prev_ts)  # type: ignore[attr-defined]
            except Exception:
                pass
            # Aggregate
            total_baseline = sum(b for b,_ in self._tuner_window)
            total_temporal = sum(t for _,t in self._tuner_window)
            if total_baseline <= 0 or total_baseline < int(runtime_params.get_param("fusion.temporal.tuner.min_baseline") or 3):
                return
            uplift = total_temporal / total_baseline
            # Incorporate memory_verified_ratio (Phase3): scale effective uplift if memory confirmations strong
            mem_ratio = 0.0
            try:
                # Attempt to read gauge value (single tenant assumption for now). We scan internal metrics mapping.
                # Prometheus Gauge stores children keyed by labels; retrieve first child value.
                child_map = getattr(metrics.FUSION_MEMORY_VERIFIED_RATIO, '_metrics', {})  # type: ignore[attr-defined]
                for _k, child in child_map.items():  # pragma: no branch - first iteration
                    try:
                        mem_ratio = float(child._value.get())  # type: ignore
                        break
                    except Exception:
                        continue
            except Exception:
                mem_ratio = 0.0
            effective_uplift = uplift * (1.0 + mem_ratio)
            # Metrics export
            try:
                metrics.FUSION_TEMPORAL_TUNER_UPLIFT_RATIO.set(effective_uplift)  # type: ignore[attr-defined]
                # Emit pre/post memory precision uplift gauges (phase labels)
                metrics.FUSION_PRECISION_UPLIFT.labels(phase="pre").set(uplift)  # type: ignore[attr-defined]
                metrics.FUSION_PRECISION_UPLIFT.labels(phase="post").set(effective_uplift)  # type: ignore[attr-defined]
            except Exception:
                pass
            target = float(runtime_params.get_param("fusion.temporal.tuner.target_uplift") or 0.8)
            tol = float(runtime_params.get_param("fusion.temporal.tuner.tolerance") or 0.1)
            hysteresis_extra = float(runtime_params.get_param("fusion.temporal.tuner.hysteresis") or 0.05)
            lower = target * (1 - tol - hysteresis_extra)
            upper = target * (1 + tol + hysteresis_extra)
            # Minimum total anomalies guard (cumulative) additional to baseline gate
            min_anom = int(runtime_params.get_param("fusion.temporal.tuner.min_anomalies") or 10)
            total_temporal = sum(t for _, t in self._tuner_window)
            if total_temporal < min_anom:
                return
            if lower <= effective_uplift <= upper:
                return  # within band
            # Determine direction
            cur_w = float(runtime_params.get_param("detection.temporal.weight") or 0.0)
            if effective_uplift < lower:  # need more temporal influence
                # If currently zero, jump to seed weight
                if cur_w == 0.0:
                    new_w = float(runtime_params.get_param("fusion.temporal.tuner.seed_weight") or 0.05)
                    reason = f"tuner_seed_increase eff_uplift={effective_uplift:.3f}<lower={lower:.3f}"
                else:
                    deficit = (target - effective_uplift) / max(target, 1e-9)
                    prop = min(deficit, 1.0)
                    max_step_frac = float(runtime_params.get_param("fusion.temporal.tuner.max_step") or 0.25)
                    max_abs = float(runtime_params.get_param("fusion.temporal.tuner.max_abs_delta") or 0.3)
                    delta = min(cur_w * max_step_frac * prop, max_abs)
                    new_w = cur_w + delta
                    reason = f"tuner_increase eff_uplift={effective_uplift:.3f}<lower={lower:.3f} delta={delta:.4f}"
            else:  # effective_uplift > upper -> decrease weight
                excess = (effective_uplift - target) / max(target, 1e-9)
                prop = min(excess, 1.0)
                max_step_frac = float(runtime_params.get_param("fusion.temporal.tuner.max_step") or 0.25)
                max_abs = float(runtime_params.get_param("fusion.temporal.tuner.max_abs_delta") or 0.3)
                delta = min(cur_w * max_step_frac * prop, max_abs)
                new_w = max(0.0, cur_w - delta)
                reason = f"tuner_decrease eff_uplift={effective_uplift:.3f}>upper={upper:.3f} delta={-delta:.4f}"
            # Apply bounds
            mn = float(runtime_params.get_param("fusion.temporal.tuner.min_weight") or 0.0)
            mx = float(runtime_params.get_param("fusion.temporal.tuner.max_weight") or 2.0)
            new_w = max(mn, min(mx, new_w))
            if abs(new_w - cur_w) < 1e-9:
                return
            # Update param (audited)
            runtime_params.update_param("detection.temporal.weight", new_w, reason=reason, actor="temporal_tuner")
            try:
                metrics.FUSION_TEMPORAL_TUNER_LAST_DELTA.set(new_w - cur_w)  # type: ignore[attr-defined]
                metrics.FUSION_TEMPORAL_TUNER_LAST_WEIGHT.set(new_w)  # type: ignore[attr-defined]
                metrics.FUSION_TEMPORAL_TUNER_ADJUSTMENTS.labels(reason=reason.split()[0]).inc()  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            return

    @staticmethod
    def _norm_snn(activity: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        return max(0.0, min(1.0, (activity - threshold) / (threshold * 2.0)))

    # --- Temporal Latency Guard Update (called externally by pipeline or detectors) ---
    def record_temporal_latency(self, tenant: str, latency_s: float):  # lightweight rolling p99 approximation
        try:
            self._temporal_lat_samples.append(latency_s)
            # Compute p99 from sorted copy (bounded size)
            if len(self._temporal_lat_samples) >= 5:
                vals = sorted(self._temporal_lat_samples)
                idx = int(0.99 * (len(vals)-1))
                p99 = vals[idx]
                metrics.TEMPORAL_LATENCY_P99.labels(tenant=tenant).set(p99)  # type: ignore[attr-defined]
                thr = float(runtime_params.get_param("temporal.guard.latency_p99_s") or 0.15)
                if p99 > thr:
                    action = "pause" if bool(runtime_params.get_param("temporal.guard.pause_on_trigger")) else "degrade"
                    metrics.TEMPORAL_LATENCY_GUARD_TRIPS.labels(tenant=tenant, action=action).inc()  # type: ignore[attr-defined]
                    # Apply action: pause or weight reduce
                    if action == "pause":
                        cooldown = float(runtime_params.get_param("temporal.guard.cooldown_s") or 60.0)
                        import time as _t
                        resume_after = _t.time() + cooldown
                        self._temporal_pause_state[tenant] = resume_after
                        try:
                            metrics.TEMPORAL_PAUSE_STATE.labels(tenant=tenant).set(1)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    else:
                        # Weight degradation (halve once) audited
                        try:
                            cur_w = float(runtime_params.get_param("detection.temporal.weight") or 0.0)
                            if cur_w > 0:
                                runtime_params.update_param("detection.temporal.weight", round(cur_w * 0.5, 6), reason="temporal_latency_guard", actor="temporal_guard")
                        except Exception:
                            pass
        except Exception:
            pass

# Singleton arbitrator (lightweight)
_arbitrator: FusionArbitrator | None = None

def arbitrator() -> FusionArbitrator:
    global _arbitrator
    if _arbitrator is None:
        _arbitrator = FusionArbitrator()
    return _arbitrator

__all__ = ["FusionArbitrator", "arbitrator"]
