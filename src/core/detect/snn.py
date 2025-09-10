"""Experimental SNN detector scaffold (Phase 3).

Modular components:
- RateEncoderV1 (deterministic rate -> spike matrix generation)
- LIFPrototype (placeholder; sums spikes now, swap with real snntorch LIF later)
- ThresholdScorerV1 (simple threshold over activity)
- RiskContext (stub for future risk weighting: CVE, MITRE, asset criticality)

Design goals:
- Deterministic given input features & runtime params.
- No heavy torch import until we introduce real LIF layer (future task).
- Rich metadata for audit & compliance mapping.

Activation: Controlled by runtime param `detection.enable_snn` and pipeline import guard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Sequence, Tuple, Optional
import math, hashlib, json

from core.event import Event
from config import runtime_params
from core import metrics
import time
from .interface import IDetector, DetectionResult, registry
from core.failover.firefighter import DisableCycleWindow
from core.failover.incidents import append_incident
from .autocal import AutoCalibrator, CalibrationDecision
from core.snn.model import build_backend
from core.sequence.buffer import GLOBAL_SEQUENCE_BUFFER
from core.sequence.forecasting import ResidualForecaster

SNN_DETECTOR_VERSION = "0.1.0-experimental"


# ---- Encoder ----
class IEncoder:
    def encode(self, features: Dict[str, float]) -> Tuple[List[str], List[List[int]]]:
        """Return ordered feature keys and spike matrix [T][F] (0/1).

        Deterministic: stable feature ordering & accumulation algorithm.
        """
        raise NotImplementedError


class RateEncoderV1(IEncoder):
    def __init__(self, window: int, rate_scale: float):
        self.window = max(1, int(window))
        self.rate_scale = float(rate_scale)

    @staticmethod
    def _median(vals: Sequence[float]) -> float:
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return 0.0
        m = n // 2
        return s[m] if n % 2 == 1 else (s[m - 1] + s[m]) / 2

    def _scale(self, vec: List[float]) -> List[float]:
        if not vec:
            return []
        mags = [abs(x) for x in vec]
        med = self._median(mags)
        devs = [abs(x - med) for x in mags]
        mad = self._median(devs) or 1.0
        ref = med + mad
        ref = ref if ref > 1e-9 else 1.0
        # tanh scaling
        scaled = [math.tanh(x / (ref * 3.0)) for x in vec]
        return [abs(x) for x in scaled]  # magnitude only v1

    def encode(self, features: Dict[str, float]) -> Tuple[List[str], List[List[int]]]:
        keys = sorted(k for k, v in features.items() if isinstance(v, (int, float)))
        vec = [float(features[k]) for k in keys]
        scaled = self._scale(vec)
        T = self.window
        spikes: List[List[int]] = [[0 for _ in keys] for _ in range(T)]
        if not keys:
            return keys, spikes
        for j, val in enumerate(scaled):
            base_rate = max(0.0, min(self.rate_scale, val * self.rate_scale))
            acc = 0.0
            for t in range(T):
                acc += base_rate
                # Epsilon compensate to avoid losing a spike due to floating rounding (e.g., 0.05 * 20)
                if acc + 1e-9 >= 1.0:
                    spikes[t][j] = 1
                    acc -= 1.0
        return keys, spikes


class RateEncoderV2(IEncoder):
    """Robust adaptive rate encoder.

    Upgrades over v1:
      - Robust scaling: median & MAD per event (across features) for magnitude normalization.
      - Burst gating: feature values that exceed (median + k * MAD) get a transient boost factor.
      - Density cap: ensure overall spike density does not exceed a soft cap by proportional rate shrink.
    Deterministic: operates only on current feature snapshot (stateless apart from constants).
    """
    def __init__(self, window: int, rate_scale: float, burst_k: float = 3.0, burst_boost: float = 1.8, density_cap: float = 0.35):
        self.window = max(1, int(window))
        self.rate_scale = float(rate_scale)
        self.burst_k = float(burst_k)
        self.burst_boost = float(burst_boost)
        self.density_cap = float(density_cap)
        self._printed_zero_after_floor = False  # debug one-time flag

    @staticmethod
    def _median(vals: Sequence[float]) -> float:
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return 0.0
        m = n // 2
        return s[m] if n % 2 == 1 else (s[m - 1] + s[m]) / 2

    def encode(self, features: Dict[str, float]) -> Tuple[List[str], List[List[int]]]:
        keys = sorted(k for k, v in features.items() if isinstance(v, (int, float)))
        T = self.window
        spikes: List[List[int]] = [[0 for _ in keys] for _ in range(T)]
        if not keys:
            return keys, spikes
        # Initialize debug flags early to avoid unbound reference in diagnostic branches
        debug_flag = False
        debug_no_cap = False
        try:
            from config import runtime_params as _rp_flags
            debug_flag = bool(_rp_flags.get_param("snn.encoder.rate_v2.debug") or False)
            debug_no_cap = bool(_rp_flags.get_param("snn.encoder.rate_v2.debug_no_cap") or False)
        except Exception:
            pass
        vals = [abs(float(features[k])) for k in keys]
        med = self._median(vals)
        devs = [abs(v - med) for v in vals]
        mad = self._median(devs) or 1.0
        ref = med + mad
        ref = ref if ref > 1e-9 else 1.0
        # First pass: compute preliminary normalized magnitudes
        mags: List[float] = []
        for v in vals:
            norm = v / ref
            # Burst gating threshold
            if v > med + self.burst_k * mad:
                norm *= self.burst_boost
            mags.append(min(norm, 10.0))
        # Convert to base rates
        rates = [min(self.rate_scale, math.tanh(m) * self.rate_scale) for m in mags]
        # If debug flag and all rates ~0 but mags have variance, try raw proportional scaling (diagnostic)
        if debug_flag and all(r < 1e-6 for r in rates) and (max(mags) - min(mags)) > 0:
            raw_max = max(mags) or 1.0
            rates = [min(self.rate_scale, (m / raw_max) * self.rate_scale) for m in mags]
            try:
                print(f"[rate_v2.debug] proportional_fallback_rates={rates} raw_mags={mags}")
            except Exception:
                pass
        # Secondary linear fallback
        if debug_flag and all(r < 1e-6 for r in rates) and any(m > 0 for m in mags):
            rates = [min(self.rate_scale, m / 3.0 * self.rate_scale) for m in mags]
            try:
                print(f"[rate_v2.debug] linear_fallback_rates={rates}")
            except Exception:
                pass
        # Apply global shrink param (fetched lazily to avoid coupling during init)
        try:
            from config import runtime_params as _rp  # local import to prevent cycles
            shrink = float(_rp.get_param("snn.encoder.rate_v2.global_shrink") or 0.1)
            min_floor = float(_rp.get_param("snn.encoder.rate_v2.min_floor") or 0.0)
            # debug flags already populated earlier
        except Exception:
            shrink = 0.1
            min_floor = 0.0
            # keep prior debug flags
        shrink = max(0.01, min(1.0, shrink))
        if debug_flag:
            try:
                print(f"[rate_v2.debug] mags={mags} med={med:.6f} mad={mad:.6f} ref={ref:.6f} pre_shrink_rates={rates} shrink={shrink} min_floor={min_floor}")
            except Exception:
                pass
        rates = [r * shrink for r in rates]
        if min_floor > 0:
            # Enforce at least one spike per window if a feature would otherwise have a positive but tiny rate
            effective_floor = max(min_floor, 1.0 / T)
            effective_floor = max(0.0, min(0.5, effective_floor))  # hard safety upper bound
            new_rates: List[float] = []
            for j, r in enumerate(rates):
                if r > 0 and r >= effective_floor:
                    new_rates.append(r)
                elif (r > 0 and r < effective_floor) or (r == 0 and mags[j] > 0):
                    new_rates.append(effective_floor)
                else:
                    new_rates.append(0.0)
            rates = new_rates
        # Post-floor one-time zero check
        if debug_flag and not self._printed_zero_after_floor and all(r == 0 for r in rates) and any(m > 0 for m in mags):
            self._printed_zero_after_floor = True
            try:
                print(f"[rate_v2.debug] WARNING all rates zero after floor enforcement. mags={mags} ref={ref} shrink={shrink} min_floor={min_floor}")
            except Exception:
                pass
        # Safeguard: if still zero and debug, force minimal effective floor for non-zero mags
        if debug_flag and all(r == 0 for r in rates) and any(m > 0 for m in mags):
            effective_floor = max(min_floor, 1.0 / T)
            effective_floor = max(0.0, min(0.25, effective_floor))
            rates = [effective_floor if m > 0 else 0.0 for m in mags]
            try:
                print(f"[rate_v2.debug] forced_min_floor_rates={rates}")
            except Exception:
                pass
        # Density cap: estimate projected density if all rates used as-is
        projected_spikes = sum(r * T for r in rates)  # approximate expected spikes
        max_spikes = self.density_cap * T * max(1, len(keys))
        if not debug_no_cap and projected_spikes > max_spikes and projected_spikes > 0:
            shrink2 = max_spikes / projected_spikes
            rates = [r * shrink2 for r in rates]
            if debug_flag:
                try:
                    print(f"[rate_v2.debug] density_cap_applied factor={shrink2:.4f}")
                except Exception:
                    pass
        if debug_flag:
            try:
                print(f"[rate_v2.debug] post_shrink_floor_rates={rates} projected_spikes={projected_spikes:.3f}")
            except Exception:
                pass
        # Accumulate fractional spikes deterministically
        for j, r in enumerate(rates):
            acc = 0.0
            for t in range(T):
                acc += r
                if acc + 1e-9 >= 1.0:  # epsilon for rounding safety
                    spikes[t][j] = 1
                    acc -= 1.0
        return keys, spikes


# ---- Spiking Model (placeholder) ----
class ISpikingModel:
    def forward(self, spikes: List[List[int]]) -> float:
        """Return activity scalar A."""
        raise NotImplementedError


class LIFPrototype(ISpikingModel):
    def __init__(self, decay: float):
        self.decay = decay

    def forward(self, spikes: List[List[int]]) -> float:
        v = 0.0
        for timestep in spikes:
            s_sum = sum(timestep)
            v = v * self.decay + s_sum
        return v


class LIFTorch(ISpikingModel):
    """snntorch-backed simple single-layer LIF network.

    Only instantiated if torch + snntorch import succeeds and mode == lif.
    Produces an aggregate activity = mean membrane potential of final step.
    """
    def __init__(self, hidden_size: int, decay: float):
        try:  # heavy imports guarded
            import torch  # type: ignore
            import snntorch as snn  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise RuntimeError("snntorch not available for LIF mode") from e
        self.torch = __import__("torch")
        self.snn = __import__("snntorch")
        self.decay = decay
        self.hidden_size = hidden_size
        self.lif = self.snn.Leaky(beta=decay)

    def forward(self, spikes: List[List[int]]) -> float:
        import torch  # type: ignore
        if not spikes:
            return 0.0
        T = len(spikes)
        F = len(spikes[0]) if T else 0
        x = torch.tensor(spikes, dtype=torch.float32)  # [T,F]
        # Simple projection to hidden
        W = torch.ones((F, self.hidden_size), dtype=torch.float32) / max(1, F)
        h = x @ W  # [T, H]
        mem = torch.zeros(self.hidden_size)
        spk = torch.zeros(self.hidden_size)
        last_mem: Optional[float] = 0.0
        for t in range(T):
            spk, mem = self.lif(h[t], mem)
            last_mem = float(mem.mean().item())
        return float(last_mem or 0.0)


# ---- Scorer ----
class IScorer:
    def score(self, activity: float, threshold: float) -> float:
        raise NotImplementedError


class ThresholdScorerV1(IScorer):
    def score(self, activity: float, threshold: float) -> float:
        return max(0.0, activity - threshold)


# ---- Risk Context Stub ----
@dataclass
class RiskContext:
    cve_multiplier: float = 1.0
    mitre_weight: float = 1.0
    other_factors: Dict[str, float] | None = None

    def apply(self, raw_score: float) -> float:
        mult = self.cve_multiplier * self.mitre_weight
        if self.other_factors:
            for v in self.other_factors.values():
                mult *= v
        return raw_score * mult


# ---- Detector ----
class SNNDetector(IDetector):
    name = "snn"

    def __init__(self):
        window = runtime_params.get_param("snn.encoding_window") or 20
        rate_scale = runtime_params.get_param("snn.rate_scale") or 1.0
        decay = runtime_params.get_param("snn.lif_decay") or 0.95
        threshold = runtime_params.get_param("snn.threshold") or 1.0
        mode = runtime_params.get_param("snn.mode") or "proto"
        hidden = runtime_params.get_param("snn.lif.hidden_size") or 32
        self.mode = str(mode)
        encoder_sel = str(runtime_params.get_param("snn.encoder") or "rate_v1")
        if encoder_sel == "rate_v2":
            self.encoder = RateEncoderV2(window=window, rate_scale=rate_scale)  # type: ignore[assignment]
            self.encoder_name = "rate_v2"
        else:
            self.encoder = RateEncoderV1(window=window, rate_scale=rate_scale)
            self.encoder_name = "rate_v1"
        # Replace inline model selection with backend abstraction
        self.model = build_backend()
        self.scorer = ThresholdScorerV1()
        self.threshold = float(threshold)
        self.version = SNN_DETECTOR_VERSION
        # Resource guard state
        self._disabled_until: float | None = None
        self._last_latency_samples: list[float] = []
        self._latency_window = 50  # fixed small window for p95 estimation
        self._last_spike_density: float = 0.0
        # Firefighter disable cycle tracker (shared single-instance acceptable for prototype)
        self._disable_cycles = DisableCycleWindow()
        # Auto calibration state (legacy counters retained; logic removed)
        # These will be consumed by forthcoming AutoCalibrator component.
        self._events_seen = 0
        self._anoms_seen = 0
        self._baseline_anoms_seen = 0  # placeholder for future baseline overlap injection
        self._last_calibration = 0  # inert until AutoCalibrator integrated
        self._calibrator = AutoCalibrator()
        self._last_cal_decision = None
        # Sequence residual forecaster (lazy activation)
        self._forecaster = ResidualForecaster()
        # Residual rolling stats (positive contributions only)
        self._residual_contrib_sum = 0.0
        self._residual_contrib_count = 0

    def process(self, event: Event) -> List[DetectionResult]:
        now = time.time()
        if self._disabled_until and now < self._disabled_until:
            return []
        start = time.perf_counter()
        feats = {k: v for k, v in event.features.items() if isinstance(v, (int, float))}
        # Add value stream to global sequence buffer if specific feature 'value' present
        if 'value' in feats:
            try:
                GLOBAL_SEQUENCE_BUFFER.add(event.tenant_id, float(feats['value']))
            except Exception:
                pass
        keys, spike_matrix = self.encoder.encode(feats)
        activity = self.model.forward(spike_matrix)
        # Determine if internal debug printing should occur (tie to encoder v2 debug flag)
        try:
            dbg_enc = bool(runtime_params.get_param("snn.encoder.rate_v2.debug") or False)
        except Exception:
            dbg_enc = False
        # Optional residual integration
        try:
            if bool(runtime_params.get_param("seq.forecaster.enable")) and 'value' in feats:
                series = GLOBAL_SEQUENCE_BUFFER.tail(event.tenant_id)
                if series:
                    residual = self._forecaster.residual(series[-1])
                else:
                    residual = 0.0
                if residual > 0:
                    contrib = math.tanh(residual)
                    activity += contrib
                    self._residual_contrib_sum += contrib
                    self._residual_contrib_count += 1
                    try:
                        metrics.SNN_RESIDUAL_ACTIVITY.labels(tenant=event.tenant_id).set(contrib)  # type: ignore[attr-defined]
                        if self._residual_contrib_count > 0:
                            mean_val = self._residual_contrib_sum / self._residual_contrib_count
                            metrics.SNN_RESIDUAL_CONTRIB_MEAN.labels(tenant=event.tenant_id).set(mean_val)  # type: ignore[attr-defined]
                    except Exception:
                        pass
        except Exception:
            pass
        raw_score = self.scorer.score(activity, self.threshold)
        risk_ctx = RiskContext()
        final_score = risk_ctx.apply(raw_score)
        duration = time.perf_counter() - start

        # Metrics & resource guard (best-effort)
        try:
            metrics.SNN_INFERENCE_LATENCY.observe(duration)  # type: ignore[attr-defined]
            spike_count_m = sum(sum(row) for row in spike_matrix)
            Tm = len(spike_matrix)
            Fm = len(keys) or 1
            density_m = spike_count_m / (Tm * Fm) if Tm > 0 else 0.0
            self._last_spike_density = density_m
            metrics.SNN_SPIKE_DENSITY.labels(tenant=event.tenant_id).set(density_m)  # type: ignore[attr-defined]
            metrics.SNN_ACTIVITY.labels(tenant=event.tenant_id).set(activity)  # type: ignore[attr-defined]
            metrics.SNN_ENERGY_SPIKES_TOTAL.labels(tenant=event.tenant_id).inc(spike_count_m)  # type: ignore[attr-defined]
            try:
                alpha = float(runtime_params.get_param("snn.prediction.alpha") or 0.7)
            except Exception:
                alpha = 0.7
            prev = getattr(self, "_prev_activity", activity)
            predicted = alpha * activity + (1 - alpha) * prev
            self._prev_activity = activity
            metrics.SNN_PREDICTED_ACTIVITY.labels(tenant=event.tenant_id).set(predicted)  # type: ignore[attr-defined]
            self._last_latency_samples.append(duration)
            if len(self._last_latency_samples) > self._latency_window:
                self._last_latency_samples.pop(0)
            if evaluate_resource_guard(self._last_latency_samples, density_m):
                metrics.SNN_RESOURCE_GUARDS_TRIGGERED.labels(reason="resource_guard").inc()  # type: ignore[attr-defined]
                cooldown = runtime_params.get_param("snn.guard.cooldown_s") or 30.0
                self._disabled_until = time.time() + float(cooldown)
                try:
                    self._disable_cycles.add_disable()
                    incident = self._disable_cycles.evaluate()
                    if incident:
                        append_incident(incident)
                except Exception:
                    pass
                return []
            if self._disabled_until and time.time() >= self._disabled_until:
                self._disabled_until = None
        except Exception:
            pass

        # Counting for auto-calibration
        self._events_seen += 1
        if final_score > 0:
            self._anoms_seen += 1

        # Inline auto-calibration logic removed (legacy). Threshold now static until external AutoCalibrator is integrated.

        # External auto-calibration (interval-based deterministic) executed after metrics, before emission
        try:
            decision = self._calibrator.maybe_adjust(
                events_seen=self._events_seen,
                snn_anoms=self._anoms_seen,
                baseline_anoms=self._baseline_anoms_seen,
                current_threshold=self.threshold,
                get_param=runtime_params.get_param,
            )
            self._last_cal_decision = decision
            if decision.changed:
                self.threshold = decision.new_threshold
            try:
                # Increment decision metric (reason label) best-effort
                metrics.SNN_AUTO_CAL_DECISIONS_TOTAL.labels(reason=decision.reason).inc()  # type: ignore[attr-defined]
            except Exception:
                pass
                if dbg_enc:
                    try:
                        print(f"[snn.debug] ev={event.event_id} spikes={spike_count_m} activity={activity:.4f} threshold={self.threshold:.4f} density={density_m:.4f}")
                    except Exception:
                        pass
        except Exception:
            pass

        if final_score <= 0:
            return []
        feature_repr = json.dumps({k: feats.get(k) for k in keys}, sort_keys=True)
        feat_hash = hashlib.sha256(feature_repr.encode("utf-8")).hexdigest()[:16]
        spike_count = sum(sum(row) for row in spike_matrix)
        T = len(spike_matrix)
        F = len(keys)
        density = spike_count / (max(1, T * max(1, F)))
        result = DetectionResult({
            "detector": self.name,
            "version": self.version,
            "tenant": event.tenant_id,
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "score": final_score,
            "raw_score": raw_score,
            "activity": activity,
            "mode": self.mode,
            "threshold": self.threshold,
            "features_hash": feat_hash,
            "feature_count": F,
            "time_window": T,
            "spike_count": spike_count,
            "spike_density": density,
            "encoder": self.encoder_name,
            "model": "lif_torch" if self.mode.startswith("lif") else "lif_prototype",
            "scorer": "threshold_v1",
            "risk_applied": risk_ctx.cve_multiplier != 1.0 or risk_ctx.mitre_weight != 1.0,
            "inference_latency_s": duration,
            "auto_cal_reason": getattr(self._last_cal_decision, "reason", None),
            "auto_cal_uplift_ratio": getattr(self._last_cal_decision, "uplift_ratio", None),
        })
        return [result]


def register_snn() -> SNNDetector:
    det = SNNDetector()
    registry.register(det)
    return det


# --- Resource guard enhanced logic ---
def evaluate_resource_guard(latency_samples: list[float], current_density: float) -> bool:
    """Return True if guard should trigger.

    Criteria (any):
      - p95 latency over window exceeds runtime param snn.guard.max_latency_s
      - current spike density exceeds snn.guard.max_spike_density
    """
    try:
        max_lat = runtime_params.get_param("snn.guard.max_latency_s") or 0.25
        max_density = runtime_params.get_param("snn.guard.max_spike_density") or 0.8
    except Exception:
        max_lat, max_density = 0.25, 0.8
    if latency_samples:
        sorted_l = sorted(latency_samples)
        idx = int(0.95 * (len(sorted_l) - 1))
        p95 = sorted_l[idx]
        if p95 > max_lat:
            return True
    if current_density > max_density:
        return True
    return False


__all__ = [
    "SNN_DETECTOR_VERSION",
    "SNNDetector",
    "register_snn",
    "RateEncoderV1",
    "LIFPrototype",
    "ThresholdScorerV1",
    "RiskContext",
    "evaluate_resource_guard",
]
