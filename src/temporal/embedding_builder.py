"""Temporal Embedding Builder (spec version 0.1.0)

Implements deterministic feature extraction per docs/TEMPORAL_EMBEDDING_SPEC.md.

Public function:
    build_embedding(points: list[dict], *, get_param, now_fn=time.time) -> dict

Determinism Rules:
 - Input list of points mutated only by defensive sort (ascending ts) and NaN filter.
 - Floating outputs rounded to 6 decimal places.
 - Hash excludes the 'hash' field itself and '_meta'.
 - On error computing a feature, value set to None (JSON null) but key retained.

Minimal Mode:
 - If length < embedding.min_length returns {'version', 'length', 'reason', 'hash', 'canonical_order', '_meta'}.

NOTE: No external numeric heavy libs to keep footprint small; uses stdlib only.
"""
from __future__ import annotations

from typing import List, Dict, Callable, Sequence
import math, hashlib, json, time, statistics

EMBEDDING_VERSION = "0.1.0"
FLOAT_FMT = "{:.6f}"  # uniform rounding

# --- Helpers ---

def _safe_float(x):
    try:
        if x is None:
            return None
        xf = float(x)
        if math.isnan(xf) or math.isinf(xf):
            return None
        return xf
    except Exception:
        return None


def _median(vals: Sequence[float]) -> float:
    n = len(vals)
    if n == 0:
        return 0.0
    s = sorted(vals)
    m = n // 2
    if n % 2:
        return s[m]
    return (s[m - 1] + s[m]) / 2


def _mad(vals: Sequence[float], med: float | None = None) -> float:
    if not vals:
        return 0.0
    if med is None:
        med = _median(vals)
    devs = [abs(v - med) for v in vals]
    return _median(devs)


def _percentile(vals: Sequence[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _autocorr(vals: Sequence[float], lag: int) -> float:
    n = len(vals)
    if lag <= 0 or n <= lag:
        return 0.0
    mean = sum(vals) / n
    num = 0.0
    den = 0.0
    for v in vals:
        den += (v - mean) ** 2
    if den == 0:
        return 0.0
    for i in range(n - lag):
        num += (vals[i] - mean) * (vals[i + lag] - mean)
    return num / den


def _fft_energy_ratio(vals: Sequence[float]) -> float:
    # Coarse DFT (O(N^2)) acceptable for small N typical of embedding window.
    N = len(vals)
    if N <= 1:
        return 0.0
    mean = sum(vals) / N
    centered = [v - mean for v in vals]
    total_var = sum(v * v for v in centered)
    if total_var == 0:
        return 0.0
    max_power = 0.0
    # Frequencies 1..N//2
    for k in range(1, N // 2 + 1):
        re = 0.0
        im = 0.0
        for n, v in enumerate(centered):
            angle = 2 * math.pi * k * n / N
            re += v * math.cos(angle)
            im += v * math.sin(angle)
        power = re * re + im * im
        if power > max_power:
            max_power = power
    return max_power / total_var if max_power > 0 else 0.0


def _ols(vals: Sequence[float], ts: Sequence[float]):
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    # Shift time to start at zero for numerical stability
    t0 = ts[0]
    xs = [t - t0 for t in ts]
    mean_x = sum(xs) / n
    mean_y = sum(vals) / n
    num = 0.0
    den = 0.0
    for x, y in zip(xs, vals):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        den += dx * dx
    slope = num / den if den != 0 else 0.0
    # residual std
    resid_sq_sum = 0.0
    for x, y in zip(xs, vals):
        pred = mean_y + slope * (x - mean_x)
        resid_sq_sum += (y - pred) ** 2
    resid_std = math.sqrt(resid_sq_sum / n) if n > 0 else 0.0
    return slope, resid_std


def _format_float(v: float | None) -> float | None:
    if v is None:
        return None
    try:
        return float(FLOAT_FMT.format(v))
    except Exception:
        return None

# --- Main Builder ---


def build_embedding(points: List[Dict], *, get_param: Callable[[str], float | int | bool | None], now_fn=time.time) -> Dict:
    """Build temporal embedding from sequence of {ts, value} points.

    Returns embedding dict per spec. Deterministic for same sorted input & params.
    """
    raw = []
    nan_dropped = 0
    for p in points:
        ts = _safe_float(p.get("ts"))
        val = _safe_float(p.get("value"))
        if ts is None or val is None:
            nan_dropped += 1
            continue
        raw.append((ts, val))
    raw.sort(key=lambda x: x[0])
    N = len(raw)
    min_length = int(get_param("embedding.min_length") or 5)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_fn()))
    if N < min_length:
        base = {
            "version": EMBEDDING_VERSION,
            "length": N,
            "reason": "too_short",
            "nan_dropped": nan_dropped,
        }
        # Minimal canonical
        ordered = sorted(base.keys())
        canonical_str = json.dumps({k: base[k] for k in ordered}, separators=(",", ":"), sort_keys=True)
        full_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        base["hash"] = full_hash[:16]
        base["canonical_order"] = ordered
        base["_meta"] = {"generated_at": now_iso, "builder_version": EMBEDDING_VERSION}
        return base
    ts_list = [t for t, _ in raw]
    vals = [v for _, v in raw]
    # Time deltas
    dts = [ts_list[i] - ts_list[i - 1] for i in range(1, N)]
    try:
        window_seconds = ts_list[-1] - ts_list[0]
        mean_dt = sum(dts) / len(dts) if dts else 0.0
        stdev_dt = math.sqrt(sum((dt - mean_dt) ** 2 for dt in dts) / len(dts)) if dts else 0.0
        jitter_coef = stdev_dt / mean_dt if mean_dt > 0 else 0.0
    except Exception:
        window_seconds = mean_dt = jitter_coef = 0.0
    # Basic stats
    try:
        mean_v = sum(vals) / N if N else 0.0
        median_v = _median(vals)
        # Population std
        std_v = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / N) if N else 0.0
        mad_v = _mad(vals, median_v)
        min_v = min(vals) if vals else 0.0
        max_v = max(vals) if vals else 0.0
        p95_v = _percentile(vals, 0.95)
        sorted_vals = sorted(vals)
        q1 = _percentile(sorted_vals, 0.25)
        q3 = _percentile(sorted_vals, 0.75)
        iqr = q3 - q1
    except Exception:
        mean_v = median_v = std_v = mad_v = min_v = max_v = p95_v = iqr = 0.0
    # Trend
    try:
        slope, resid_std = _ols(vals, ts_list)
    except Exception:
        slope = resid_std = 0.0
    # Diff-based
    diffs = [vals[i] - vals[i - 1] for i in range(1, N)]
    try:
        if diffs:
            mean_abs_diff = sum(abs(d) for d in diffs) / len(diffs)
            diff_std = math.sqrt(sum((d - (sum(diffs)/len(diffs))) ** 2 for d in diffs) / len(diffs))
        else:
            mean_abs_diff = diff_std = 0.0
    except Exception:
        mean_abs_diff = diff_std = 0.0
    burst_sigma = float(get_param("embedding.burst_sigma") or 2.5)
    try:
        burst_count = 0
        burst_total = 0.0
        if diff_std > 0:
            for d in diffs:
                if abs(d) > burst_sigma * diff_std:
                    burst_count += 1
                    burst_total += abs(d)
    except Exception:
        burst_count = 0
        burst_total = 0.0
    # Volatility
    try:
        vol_normalized = std_v / (abs(mean_v) + 1e-9)
        change_index = mean_abs_diff / (abs(mean_v) + 1e-9)
    except Exception:
        vol_normalized = change_index = 0.0
    # Autocorr
    try:
        ac1 = _autocorr(vals, 1)
        ac2 = _autocorr(vals, 2)
    except Exception:
        ac1 = ac2 = 0.0
    enable_fft = bool(get_param("embedding.enable_fft") if get_param("embedding.enable_fft") is not None else True)
    try:
        energy_ratio = _fft_energy_ratio(vals) if enable_fft else 0.0
    except Exception:
        energy_ratio = 0.0
    # Stability
    try:
        value_cv = std_v / (abs(mean_v) + 1e-9)
        # z-run
        z_threshold = float(get_param("embedding.z_run_threshold") or 1.5)
        if std_v == 0:
            z_run_mean = 0.0
        else:
            runs = []
            current = 0
            for v in vals:
                z = (v - mean_v) / std_v
                if abs(z) > z_threshold:
                    current += 1
                else:
                    if current > 0:
                        runs.append(current)
                        current = 0
            if current > 0:
                runs.append(current)
            z_run_mean = (sum(runs) / len(runs)) if runs else 0.0
    except Exception:
        value_cv = z_run_mean = 0.0
    # Sparsity / density
    try:
        non_zero_ratio = sum(1 for v in vals if v != 0) / N if N else 0.0
        positive_ratio = sum(1 for v in vals if v > 0) / N if N else 0.0
    except Exception:
        non_zero_ratio = positive_ratio = 0.0

    embed = {
        "version": EMBEDDING_VERSION,
        "length": N,
        "window_seconds": _format_float(window_seconds),
        "sampling.mean_dt": _format_float(mean_dt),
        "sampling.jitter_coef": _format_float(jitter_coef),
        "value.mean": _format_float(mean_v),
        "value.median": _format_float(median_v),
        "value.std": _format_float(std_v),
        "value.mad": _format_float(mad_v),
        "value.min": _format_float(min_v),
        "value.max": _format_float(max_v),
        "value.p95": _format_float(p95_v),
        "value.iqr": _format_float(iqr),
        "trend.slope_ols": _format_float(slope),
        "trend.residual_std": _format_float(resid_std),
        "burst.count": burst_count,
        "burst.total_magnitude": _format_float(burst_total),
        "volatility.normalized": _format_float(vol_normalized),
        "volatility.change_index": _format_float(change_index),
        "periodicity.autocorr_lag1": _format_float(ac1),
        "periodicity.autocorr_lag2": _format_float(ac2),
        "periodicity.energy_ratio": _format_float(energy_ratio),
        "stability.value_cv": _format_float(value_cv),
        "stability.z_run_mean": _format_float(z_run_mean),
        "sparsity.non_zero_ratio": _format_float(non_zero_ratio),
        "density.positive_ratio": _format_float(positive_ratio),
        "nan_dropped": nan_dropped,
    }
    ordered = sorted(embed.keys())
    canonical_payload = {k: embed[k] for k in ordered}
    canonical_str = json.dumps(canonical_payload, separators=(",", ":"), sort_keys=True)
    full_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    embed["hash"] = full_hash[:16]
    embed["canonical_order"] = ordered
    embed["_meta"] = {"generated_at": now_iso, "builder_version": EMBEDDING_VERSION}
    return embed

__all__ = ["build_embedding", "EMBEDDING_VERSION"]
