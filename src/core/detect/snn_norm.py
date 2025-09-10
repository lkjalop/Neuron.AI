"""SNN score normalization layer (percentile mapping).

Maps raw SNN anomaly scores to a stable 0..1 space using rolling
per‑tenant empirical quantiles once a minimum sample threshold is reached.

Runtime params expected (already defined in schema):
  snn.norm.enable (bool)          : master toggle
  snn.norm.window (int)           : rolling window max samples (default ~500-1000 typical)
  snn.norm.min_samples (int)      : minimum samples before mapping constructed
  snn.norm.max_stale_s (int/float): if mapping older than this, allow recompute

Metrics updated:
  SNN_NORM_UPDATES_TOTAL (counter)  – increment on mapping recompute
  SNN_NORM_MAPPING_AGE_S (gauge)    – age in seconds since last mapping update

Algorithm:
  1. Maintain deque of recent raw scores per tenant (cap at window).
  2. When (len >= min_samples) and either (no mapping) or (stale) or (enough new samples),
     compute quantile anchors at q in {0.10,0.25,0.50,0.75,0.90,0.95}.
  3. Store mapping: list of (raw_value, q) pairs sorted by raw_value.
  4. normalize(score): piecewise linear interpolation over anchors mapping raw_value -> q.
     Below min anchor => 0.0; above max anchor => 1.0.
  5. If disabled / insufficient samples / invalid score -> return original score.

Edge handling: NaN/inf ignored; duplicate raw anchor values collapsed.

Intentionally lightweight & defensive; failures degrade to returning raw score.
"""
from __future__ import annotations

from collections import deque
import math, time
from typing import Deque, Dict, List, Tuple, Optional

try:  # metrics optional in unit tests
    from core import metrics as _m  # type: ignore
except Exception:  # pragma: no cover
    _m = None  # type: ignore

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
_DEFAULT_WINDOW = 600
_MIN_SAMPLES_FALLBACK = 120
_RECOMPUTE_FRACTION = 0.15  # recompute when this fraction of window new samples since last compute
_MAX_RECOMPUTE_INTERVAL = 30.0  # seconds (safety guard)

class _TenantNormState:
    __slots__ = ["window", "mapping", "last_update_ts", "last_len"]
    def __init__(self, maxlen: int):
        self.window: Deque[float] = deque(maxlen=maxlen)
        self.mapping: List[Tuple[float, float]] | None = None  # (raw_value, q)
        self.last_update_ts: float | None = None
        self.last_len: int = 0

class SNNNormalizer:
    def __init__(self):
        self._tenants: Dict[str, _TenantNormState] = {}

    # ---- param helpers ----
    def _enabled(self) -> bool:
        try:
            if runtime_params:
                val = runtime_params.get_param("snn.norm.enable")
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.lower() in {"1","true","yes","on"}
        except Exception:
            pass
        return False

    def _window(self) -> int:
        try:
            if runtime_params:
                v = runtime_params.get_param("snn.norm.window")
                if isinstance(v, (int,float)) and v > 10:
                    return int(min(5000, max(50, v)))
        except Exception:
            pass
        return _DEFAULT_WINDOW

    def _min_samples(self) -> int:
        try:
            if runtime_params:
                v = runtime_params.get_param("snn.norm.min_samples")
                if isinstance(v, (int,float)) and v >= 10:
                    return int(v)
        except Exception:
            pass
        return _MIN_SAMPLES_FALLBACK

    def _max_stale(self) -> float:
        try:
            if runtime_params:
                v = runtime_params.get_param("snn.norm.max_stale_s")
                if isinstance(v, (int,float)) and v > 0:
                    return float(min(3600, v))
        except Exception:
            pass
        return 300.0

    # ---- core update / compute ----
    def _state(self, tenant: str) -> _TenantNormState:
        st = self._tenants.get(tenant)
        w = self._window()
        if not st:
            st = _TenantNormState(maxlen=w)
            self._tenants[tenant] = st
        # adapt window size if param changed
        if st.window.maxlen != w:
            newdq: Deque[float] = deque(st.window, maxlen=w)
            st.window = newdq
        return st

    def _maybe_recompute(self, tenant: str, st: _TenantNormState) -> None:
        now = time.time()
        min_samples = self._min_samples()
        n = len(st.window)
        if n < min_samples:
            return
        stale = False
        if st.last_update_ts is None:
            stale = True
        else:
            age = now - st.last_update_ts
            if age >= self._max_stale():
                stale = True
            elif n - st.last_len >= max(10, int(self._window() * _RECOMPUTE_FRACTION)):
                stale = True
            elif age >= _MAX_RECOMPUTE_INTERVAL:
                stale = True
        if not stale:
            return
        # compute quantiles
        try:
            data = list(st.window)
            data.sort()
            anchors: List[Tuple[float,float]] = []
            for q in _QUANTILES:
                idx = min(len(data)-1, max(0, int(round(q * (len(data)-1)))))
                val = data[idx]
                anchors.append((val, q))
            # collapse duplicates by keeping highest q for same raw value
            collapsed: Dict[float,float] = {}
            for raw, q in anchors:
                # handle NaN skip
                if raw is None or isinstance(raw, float) and math.isnan(raw):
                    continue
                prev = collapsed.get(raw)
                if prev is None or q > prev:
                    collapsed[raw] = q
            mapping = sorted((r, q) for r, q in collapsed.items())
            if mapping:
                st.mapping = mapping
                st.last_update_ts = now
                st.last_len = n
                if _m:
                    try:
                        _m.SNN_NORM_UPDATES_TOTAL.labels(tenant=tenant).inc()  # type: ignore[attr-defined]
                        _m.SNN_NORM_MAPPING_AGE_S.labels(tenant=tenant).set(0.0)  # reset age
                    except Exception:
                        pass
        except Exception:
            pass

    # ---- public API ----
    def normalize(self, score: float, tenant: str, update: bool = True) -> float:
        """Return normalized score (0..1) or raw score if not available.

        update: if True, raw score is added to rolling window before normalization attempt.
        """
        # Fast-path checks
        if not self._enabled():
            return score
        try:
            if score is None or isinstance(score, float) and (math.isnan(score) or math.isinf(score)):
                return score
            st = self._state(tenant or "_global")
            if update:
                try:
                    st.window.append(float(score))
                except Exception:
                    pass
            # Recompute mapping if required
            self._maybe_recompute(tenant, st)
            if st.mapping is None:
                return score
            # Age metric
            if _m and st.last_update_ts:
                try:
                    _m.SNN_NORM_MAPPING_AGE_S.labels(tenant=tenant).set(time.time() - st.last_update_ts)  # type: ignore[attr-defined]
                except Exception:
                    pass
            # Piecewise linear interpolation
            mapping = st.mapping
            if not mapping:
                return score
            # below min
            if score <= mapping[0][0]:
                return 0.0
            # above max
            if score >= mapping[-1][0]:
                return 1.0
            # find neighbors
            for i in range(1, len(mapping)):
                lo_raw, lo_q = mapping[i-1]
                hi_raw, hi_q = mapping[i]
                if lo_raw <= score <= hi_raw:
                    span = hi_raw - lo_raw
                    if span <= 0:
                        return lo_q  # duplicate anchor raw
                    frac = (score - lo_raw) / span
                    norm = lo_q + frac * (hi_q - lo_q)
                    # ensure bounds
                    if norm < 0: norm = 0.0
                    if norm > 1: norm = 1.0
                    return norm
            return score
        except Exception:
            return score

# Singleton accessor
def normalizer() -> SNNNormalizer:
    global _SNN_NORMALIZER
    try:
        return _SNN_NORMALIZER
    except NameError:
        _SNN_NORMALIZER = SNNNormalizer()  # type: ignore
        return _SNN_NORMALIZER

__all__ = ["normalizer", "SNNNormalizer"]
