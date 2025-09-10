"""Temporal / Fusion Weight Tuner Loop

Now multi-factor:
1. Unique contribution ratio (encourage weight when detector provides
    complementary signal; reduce when rarely unique).
2. Precision proxy false-positive rate (penalize detectors whose anomalies
    frequently occur inside noise windows).

History of adjustments persisted to JSONL for analyst transparency.

Environment Variables:
  TUNER_INTERVAL (s)
  TUNER_STEP (weight delta)
  TUNER_HIGH_THRESHOLD (unique ratio promote threshold)
  TUNER_LOW_THRESHOLD (unique ratio demote threshold)
  TUNER_MIN_WEIGHT / TUNER_MAX_WEIGHT
  TUNER_COOLDOWN (seconds minimum between per-detector adjustments)
  TUNER_FP_RATE_PENALTY_THRESHOLD (default 0.25)
  TUNER_FP_RATE_HARD_CAP (default 0.40)
  TUNER_FP_RATE_PENALTY_MULT (multiplier for step under FP penalty, default 1.0)
  TUNER_HISTORY_PATH (default artifacts/tuner/weight_history.jsonl)
"""
from __future__ import annotations

import os, time, json, pathlib
from runtime.param_store import get_param, set_param
from core import metrics

INTERVAL = float(os.getenv("TUNER_INTERVAL", 30))
STEP = float(os.getenv("TUNER_STEP", 0.05))
HI_THRESH = float(os.getenv("TUNER_HIGH_THRESHOLD", 0.30))
LO_THRESH = float(os.getenv("TUNER_LOW_THRESHOLD", 0.05))
MIN_WEIGHT = float(os.getenv("TUNER_MIN_WEIGHT", 0.1))
MAX_WEIGHT = float(os.getenv("TUNER_MAX_WEIGHT", 5.0))
COOLDOWN = float(os.getenv("TUNER_COOLDOWN", 120))  # seconds per detector
FP_RATE_PENALTY_THRESHOLD = float(os.getenv("TUNER_FP_RATE_PENALTY_THRESHOLD", 0.25))
FP_RATE_HARD_CAP = float(os.getenv("TUNER_FP_RATE_HARD_CAP", 0.40))
FP_RATE_PENALTY_MULT = float(os.getenv("TUNER_FP_RATE_PENALTY_MULT", 1.0))
HISTORY_PATH = pathlib.Path(os.getenv("TUNER_HISTORY_PATH", "artifacts/tuner/weight_history.jsonl"))
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

_last_change: dict[str, float] = {}


def _log_history(detector: str, old: float, new: float, *, unique_ratio: float, fp_rate: float, reason: str):
    rec = {
        "ts": time.time(),
        "detector": detector,
        "old_weight": old,
        "new_weight": new,
        "delta": round(new - old, 6),
        "unique_ratio": round(unique_ratio, 6),
        "fp_rate": round(fp_rate, 6),
        "reason": reason,
    }
    try:
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _now():
    return time.time()


def _eligible(detector: str) -> bool:
    last = _last_change.get(detector, 0)
    return (_now() - last) >= COOLDOWN


def _update(detector: str, *, unique_ratio: float, fp_rate: float):
    key = f"fusion.weight.{detector}"
    try:
        current = float(get_param(key, 1.0))
    except Exception:
        current = 1.0
    target = current
    reasons: list[str] = []

    # Precision proxy penalty first (overrides promotions if high)
    penalty_applied = False
    if fp_rate >= FP_RATE_PENALTY_THRESHOLD:
        # Scale penalty: hard cap triggers double step (or multiplier)
        mult = FP_RATE_PENALTY_MULT
        if fp_rate >= FP_RATE_HARD_CAP:
            mult = max(FP_RATE_PENALTY_MULT * 2, FP_RATE_PENALTY_MULT + 0.5)
        delta = STEP * mult
        target = max(MIN_WEIGHT, current - delta)
        penalty_applied = target != current
        reasons.append(f"fp_rate_penalty={fp_rate:.3f}")

    # Unique ratio driven adjustments only if no penalty or still room to move further downward / upward logically
    if not penalty_applied:
        if unique_ratio > HI_THRESH:
            target = min(MAX_WEIGHT, target + STEP)
            if target != current:
                reasons.append(f"unique_promote={unique_ratio:.3f}")
        elif unique_ratio < LO_THRESH:
            new_t = max(MIN_WEIGHT, target - STEP)
            if new_t != target:
                target = new_t
                reasons.append(f"unique_demote={unique_ratio:.3f}")

    if target != current and _eligible(detector):
        reason_str = ",".join(reasons) if reasons else "neutral"
        set_param(key, round(target, 3), actor="tuner", reason=reason_str)
        _last_change[detector] = _now()
        _log_history(detector, current, target, unique_ratio=unique_ratio, fp_rate=fp_rate, reason=reason_str)
        try:
            metrics.FUSION_WEIGHT_UPDATES_TOTAL.labels(strategy="temporal_tuner").inc()
        except Exception:
            pass


def _collect_metrics():
    """Return dicts: unique_ratios, fp_rates by detector (tenant aggregated by last value)."""
    unique: dict[str, float] = {}
    fp: dict[str, float] = {}
    reg = metrics.registry()
    for metric in reg.collect():  # type: ignore
        name = metric.name
        if name == metrics.DETECTOR_UNIQUE_RATIO._name:
            for sample in metric.samples:
                _, labels, value, *_ = sample
                det = labels.get("detector")
                if det:
                    unique[det] = float(value)
        elif name == metrics.PRECISION_PROXY_RATE._name:
            for sample in metric.samples:
                _, labels, value, *_ = sample
                det = labels.get("detector")
                if det:
                    fp[det] = float(value)
    return unique, fp


def main():
    print("[tuner] starting weight tuner loop interval=", INTERVAL)
    print(f"[tuner] thresholds unique_hi={HI_THRESH} unique_lo={LO_THRESH} fp_penalty={FP_RATE_PENALTY_THRESHOLD} fp_hard_cap={FP_RATE_HARD_CAP}")
    while True:
        unique, fp = _collect_metrics()
        detectors = set(unique) | set(fp)
        for det in detectors:
            _update(det, unique_ratio=unique.get(det, 0.0), fp_rate=fp.get(det, 0.0))
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
