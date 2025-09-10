"""Weight Governor (skeleton).

Applies proposals from adaptive.weight_regulator to runtime params with audit
logging. Keeps logic conservative: only adjusts when regulator proposes and
persists change via runtime_params.set_param (if available) else logs.
"""
from __future__ import annotations

import asyncio, logging, time, json
from pathlib import Path
try:
    from observability.tracing import span  # type: ignore
except Exception:  # pragma: no cover
    from contextlib import contextmanager as _cm
    def span(name: str, **tags):  # type: ignore
        @_cm
        def _s():
            yield
        return _s()
from config import runtime_params  # type: ignore
from adaptive.weight_regulator import propose_adjustment, regulator_state  # type: ignore
from core.main import executive_agg  # type: ignore
from core import metrics  # type: ignore

log = logging.getLogger("weight.governor")

# Structured adjustment log (JSONL) for governance-driven temporal weight changes.
_ADJUST_JSONL_PATH = Path("audit/TEMPORAL_WEIGHT_ADJUST_LOG.jsonl")

def _append_adjust_jsonl(record: dict):
        """Append a single JSON record to the adjustment JSONL file (best-effort).

        Record schema (current):
            ts: epoch seconds
            param: runtime param key adjusted
            from: previous value
            to: new value
            delta: signed change (to-from)
            direction: "increase"|"decrease"
            reason_code: compact machine parsable reason token
            reason: human readable string (may include thresholds & values)
            composite: governance composite value at decision
            high_threshold / low_threshold / hysteresis: governance thresholds snapshot
            cooldown_s: cooldown setting
            max_step_frac / max_abs_delta: step constraints
            min_weight / max_weight: guard rails
            shadow: whether in shadow mode (no persistence)
        Future extensions can add retrieval_drift, false_positive_proxy, etc.
        """
        try:
                _ADJUST_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
                with _ADJUST_JSONL_PATH.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception:
                pass


TARGETS = [
    {
        "param": "detection.temporal.weight",
        "metric": metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING,
        "metric_label_key": "tenant",
        "target_param": "fusion.temporal.tuner.target_uplift",
        # Optional tenant override param pattern: detection.temporal.weight.{tenant}
    },
]

# Track adjustments for policy rate limiting (key -> list[timestamps])
_ADJUST_LOG: dict[str, list[float]] = {}

def _policy_allow(key: str) -> bool:
    """Enforce max adjustments per hour via runtime param governance.weight.max_adjust_per_hour.

    Returns True if another adjustment is allowed. Cleans old entries outside 1h window.
    """
    try:
        max_adj = int(runtime_params.get_param("governance.weight.max_adjust_per_hour") or 20)
    except Exception:
        max_adj = 20
    now = time.time()
    window_start = now - 3600
    buf = _ADJUST_LOG.setdefault(key, [])
    # purge
    while buf and buf[0] < window_start:
        buf.pop(0)
    if len(buf) >= max_adj:
        return False
    buf.append(now)
    return True


def _read_observed(metric_obj, tenant: str | None = None) -> float:
    """Attempt to extract a recent numeric value from a prometheus Gauge.

    We access private samples via ._value.get() (prometheus_client API internals) as a pragmatic
    approach for governance loop; if unavailable we return 0.0.
    """
    # Direct gauge (no labels)
    try:
        return float(metric_obj._value.get())  # type: ignore[attr-defined]
    except Exception:
        pass
    # Labeled gauge path
    try:
        if tenant is not None and hasattr(metric_obj, '_metrics'):
            # Metric keys for labels stored in _metrics with tuple key (label_values)
            for k, child in metric_obj._metrics.items():  # type: ignore[attr-defined]
                # Attempt to match tenant label if present
                if isinstance(k, tuple) and tenant in k:
                    return float(child._value.get())  # type: ignore[attr-defined]
        # fallback: first sample
        for _k, child in getattr(metric_obj, '_metrics', {}).items():  # type: ignore[attr-defined]
            return float(child._value.get())  # type: ignore[attr-defined]
    except Exception:
        return 0.0
    return 0.0


async def _loop():  # pragma: no cover (timed loop)
    while True:
        try:
            if not bool(int(runtime_params.get_param("governance.weight.enable") or 0)):
                await asyncio.sleep(60)
                continue
            interval = int(runtime_params.get_param("governance.weight.interval_s") or 120)
            # Governance composite adaptive adjustment (single global pass) best-effort
            try:
                _governance_composite_adapt()
            except Exception:
                pass
            tenants = []
            # derive tenants from metrics label cache if possible
            try:
                m = TARGETS[0]["metric"]
                if hasattr(m, '_metrics'):
                    for k in m._metrics.keys():  # type: ignore[attr-defined]
                        if isinstance(k, tuple):
                            for val in k:
                                # crude heuristic: tenant labels look like 'tenantA' etc.
                                if val.startswith('tenant') and val not in tenants:
                                    tenants.append(val)
            except Exception:
                pass
            if not tenants:
                tenants = [None]  # global fallback
            for tgt in TARGETS:
                base_param = tgt["param"]
                for tenant in tenants:
                    with span("governor.evaluate", tenant=tenant or "global", param=base_param):
                        p = base_param if tenant is None else f"{base_param}.{tenant}"
                        current = runtime_params.get_param(p)
                        observed = _read_observed(tgt.get("metric"), tenant=tenant) if tgt.get("metric") else 0.0
                        target = float(runtime_params.get_param(tgt["target_param"]) or 0.8)
                        shadow = bool(int(runtime_params.get_param("governance.shadow_mode") or 0))
                        try:
                            current_f = float(current or 0.0)
                        except Exception:
                            continue
                        new_val = propose_adjustment(p, current_f, observed, target)
                        if new_val is not None:
                            if not _policy_allow(p):
                                log.info("policy_suppress_adjustment", extra={"param": p, "observed": observed, "target": target})
                                continue
                            try:
                                if shadow:
                                    log.info("shadow_weight_adjustment", extra={"param": p, "proposed": new_val, "observed": observed, "target": target, "tenant": tenant})
                                else:
                                    runtime_params.set_param(p, new_val, actor="governor")  # type: ignore[attr-defined]
                                    log.info("weight_adjusted", extra={"param": p, "value": new_val, "observed": observed, "target": target, "tenant": tenant})
                            except Exception:
                                log.warning("failed_set_param", extra={"param": p, "value": new_val, "tenant": tenant})
            await asyncio.sleep(interval)
        except Exception:
            await asyncio.sleep(120)


_TASK: asyncio.Task | None = None


def start(loop: asyncio.AbstractEventLoop):
    global _TASK
    if _TASK and not _TASK.done():
        return False
    _TASK = loop.create_task(_loop())
    return True


__all__ = ["start"]

def run_once_for_test():  # pragma: no cover (called explicitly in tests)
    """Execute a single synchronous evaluation pass for tracing tests.

    Mimics one iteration of the async loop without sleeping.
    """
    try:
        if not bool(int(runtime_params.get_param("governance.weight.enable") or 0)):
            return 0
    except Exception:
        return 0
    try:
        _governance_composite_adapt()
    except Exception:
        pass
    try:
        m = TARGETS[0]["metric"]
        tenants = []
        if hasattr(m, '_metrics'):
            for k in m._metrics.keys():  # type: ignore[attr-defined]
                if isinstance(k, tuple):
                    for val in k:
                        if val.startswith('tenant') and val not in tenants:
                            tenants.append(val)
        if not tenants:
            tenants = [None]
        for tgt in TARGETS:
            base_param = tgt["param"]
            for tenant in tenants:
                with span("governor.evaluate", tenant=tenant or "global", param=base_param):
                    p = base_param if tenant is None else f"{base_param}.{tenant}"
                    current = runtime_params.get_param(p)
                    observed = _read_observed(tgt.get("metric"), tenant=tenant) if tgt.get("metric") else 0.0
                    target = float(runtime_params.get_param(tgt["target_param"]) or 0.8)
                    try:
                        current_f = float(current or 0.0)
                    except Exception:
                        continue
                    _ = propose_adjustment(p, current_f, observed, target)
        return 1
    except Exception:
        return 0

__all__.append("run_once_for_test")

# ---------------- Governance Composite Adaptation -----------------
_LAST_GOVERNANCE_COMPOSITE_ADJUST: float | None = None

def _governance_composite_adapt():
    """Adapt `detection.temporal.weight` based on governance composite signal.

    Logic:
      - Read composite (0..1) from executive_agg.governance_composite.
      - If composite > high_threshold + hysteresis => decrease weight.
      - If composite < low_threshold - hysteresis  => increase weight.
      - Otherwise no change.
    Step size = min(current * max_step_frac, max_abs_delta) (increase or decrease).
    Bounds enforced via governance.composite.min_weight / max_weight.
    Cooldown enforced via governance.composite.cooldown_s.
    Emits metrics.FUSION_WEIGHT_UPDATES_TOTAL(strategy="governance_composite") on applied change.
    Shadow mode (governance.shadow_mode=1) logs but does not persist change.
    """
    global _LAST_GOVERNANCE_COMPOSITE_ADJUST
    try:
        composite = float(getattr(executive_agg, 'governance_composite', 0.0))
    except Exception:
        composite = 0.0
    try:
        import math
        now = time.time()
        cooldown = float(runtime_params.get_param("governance.composite.cooldown_s") or 90.0)
        if _LAST_GOVERNANCE_COMPOSITE_ADJUST and (now - _LAST_GOVERNANCE_COMPOSITE_ADJUST) < cooldown:
            return
        high_thr = float(runtime_params.get_param("governance.composite.high_threshold") or 0.75)
        low_thr = float(runtime_params.get_param("governance.composite.low_threshold") or 0.35)
        hyst = float(runtime_params.get_param("governance.composite.hysteresis") or 0.03)
        max_step_frac = float(runtime_params.get_param("governance.composite.max_step_frac") or 0.15)
        max_abs = float(runtime_params.get_param("governance.composite.max_abs_delta") or 0.15)
        min_w = float(runtime_params.get_param("governance.composite.min_weight") or 0.0)
        max_w = float(runtime_params.get_param("governance.composite.max_weight") or 1.5)
        shadow = bool(int(runtime_params.get_param("governance.shadow_mode") or 1))
        key = "detection.temporal.weight"
        try:
            cur = float(runtime_params.get_param(key) or 0.0)
        except Exception:
            return
        direction = 0.0
        reason = None
        reason_code = None
        if composite > (high_thr + hyst):
            direction = -1.0
            reason_code = "composite_high"
            reason = f"composite_high:{composite:.3f}>thr={high_thr:.3f}"  # decrease weight
        elif composite < (low_thr - hyst):
            direction = 1.0
            reason_code = "composite_low"
            reason = f"composite_low:{composite:.3f}<thr={low_thr:.3f}"  # increase weight
        if direction == 0.0:
            return  # No adjustment needed
        # compute step
        step_prop = cur * max_step_frac
        if step_prop <= 0:
            step_prop = max_step_frac * 0.05  # small seed step
        delta = min(step_prop, max_abs)
        new_v = cur + direction * delta
        new_v = max(min_w, min(max_w, new_v))
        if abs(new_v - cur) < 1e-9:
            return
        _LAST_GOVERNANCE_COMPOSITE_ADJUST = now
        # Common structured record for both shadow and active modes
        record = {
            "ts": now,
            "param": key,
            "from": cur,
            "to": new_v,
            "delta": round(new_v - cur, 12),
            "direction": "increase" if new_v > cur else "decrease",
            "reason_code": reason_code,
            "reason": reason,
            "composite": composite,
            "high_threshold": high_thr,
            "low_threshold": low_thr,
            "hysteresis": hyst,
            "cooldown_s": cooldown,
            "max_step_frac": max_step_frac,
            "max_abs_delta": max_abs,
            "min_weight": min_w,
            "max_weight": max_w,
            "shadow": shadow,
        }
        if shadow:
            log.info("governance_shadow_adjust", extra={"param": key, "from": cur, "to": new_v, "reason": reason, "composite": composite, "reason_code": reason_code})
            _append_adjust_jsonl(record)
        else:
            try:
                runtime_params.update_param(key, new_v, reason=reason or "gov_composite_adjust", actor="governor")  # type: ignore[attr-defined]
            except Exception:
                log.warning("governance_adjust_failed", extra={"param": key})
                return
            log.info("governance_adjust", extra={"param": key, "from": cur, "to": new_v, "reason": reason, "composite": composite, "reason_code": reason_code})
            _append_adjust_jsonl(record)
            try:
                metrics.FUSION_WEIGHT_UPDATES_TOTAL.labels(strategy="governance_composite").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        return

__all__.append("_governance_composite_adapt")