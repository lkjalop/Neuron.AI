from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Tuple, Any
import bisect, json, time, os, threading

_CALIBRATION_PATH = os.path.join("artifacts", "calibration", "temporal_calibration.json")
_CALIBRATION_DIR = os.path.dirname(_CALIBRATION_PATH)

_SAVE_LOCK = threading.Lock()

class QuantileCalibrator:
    """Tracks residual norms and provides rolling quantile estimates.

    For simplicity and determinism, maintains a bounded sorted list (size cap) per tenant.
    Acceptable for prototype scale; can replace with streaming GK later.
    """
    def __init__(self, max_samples: int = 500):
        self.max_samples = max_samples
        self._samples: Dict[str, Deque[float]] = {}
        self._last_update_ts: Dict[str, float] = {}
        self._loaded = False

    def add(self, tenant: str, value: float):
        dq = self._samples.setdefault(tenant, deque())
        # Insert maintaining sorted order (binary search into list form)
        lst = list(dq)
        bisect.insort(lst, float(value))
        if len(lst) > self.max_samples:
            # drop oldest extremity (pop one from each end alternately to stabilize distribution)
            lst.pop(0)
        dq.clear()
        dq.extend(lst)
        self._last_update_ts[tenant] = time.time()

    def quantiles(self, tenant: str) -> Tuple[float, float, float]:
        dq = self._samples.get(tenant)
        if not dq:
            return (0.0, 0.0, 0.0)
        lst = list(dq)
        n = len(lst)
        def q(p: float) -> float:
            if n == 0:
                return 0.0
            idx = int(p * (n - 1))
            return lst[idx]
        return (q(0.5), q(0.9), q(0.99))

    def last_update_age(self, tenant: str) -> float:
        ts = self._last_update_ts.get(tenant)
        if not ts:
            return float("inf")
        return max(0.0, time.time() - ts)

    # ---- Persistence Layer ----
    def save(self) -> None:
        with _SAVE_LOCK:
            try:
                if not os.path.isdir(_CALIBRATION_DIR):
                    os.makedirs(_CALIBRATION_DIR, exist_ok=True)
                out: Dict[str, Any] = {}
                for tenant, dq in self._samples.items():
                    lst = list(dq)
                    if not lst:
                        continue
                    p50, p90, p99 = self.quantiles(tenant)
                    out[tenant] = {
                        'samples': lst[-self.max_samples:],  # store raw slice (small scale)
                        'p50': p50,
                        'p90': p90,
                        'p99': p99,
                        'updated': self._last_update_ts.get(tenant, 0.0),
                    }
                tmp_path = _CALIBRATION_PATH + '.tmp'
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(out, f)
                os.replace(tmp_path, _CALIBRATION_PATH)
                # Optional Postgres persistence (best-effort)
                try:
                    if os.getenv("NEON_DATABASE_URL"):
                        import asyncio
                        async def _persist(items):  # type: ignore
                            try:
                                from storage import postgres  # type: ignore
                                await postgres.execute("""
                                    CREATE TABLE IF NOT EXISTS calibration_quantiles (
                                        tenant TEXT PRIMARY KEY,
                                        p50 DOUBLE PRECISION,
                                        p90 DOUBLE PRECISION,
                                        p99 DOUBLE PRECISION,
                                        updated DOUBLE PRECISION
                                    )""")
                                for t, rec in items.items():
                                    try:
                                        await postgres.execute(
                                            "INSERT INTO calibration_quantiles (tenant,p50,p90,p99,updated) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (tenant) DO UPDATE SET p50=EXCLUDED.p50,p90=EXCLUDED.p90,p99=EXCLUDED.p99,updated=EXCLUDED.updated",
                                            t, rec['p50'], rec['p90'], rec['p99'], rec['updated']
                                        )
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                        # Fire and forget background task
                        try:
                            asyncio.get_running_loop().create_task(_persist(out))
                        except RuntimeError:  # no loop (e.g., sync context) -> ignore
                            pass
                except Exception:
                    pass
            except Exception:
                pass

    def load(self, max_age_s: float = 3600.0) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            if not os.path.isfile(_CALIBRATION_PATH):
                return
            with open(_CALIBRATION_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            now = time.time()
            for tenant, rec in data.items():
                updated = float(rec.get('updated') or 0.0)
                if updated and (now - updated) > max_age_s:
                    continue  # stale
                samples = rec.get('samples') or []
                dq: Deque[float] = deque()
                for v in samples[-self.max_samples:]:
                    try:
                        dq.append(float(v))
                    except Exception:
                        continue
                if dq:
                    self._samples[tenant] = dq
                    self._last_update_ts[tenant] = updated or now
        except Exception:
            pass

    def confidence_band(self, tenant: str, value: float) -> str:
        p50, p90, p99 = self.quantiles(tenant)
        if p50 == p90 == p99 == 0:
            return "LOW"  # insufficient data
        if value >= p99:
            return "CRITICAL"
        if value >= p90:
            return "HIGH"
        if value >= p50:
            return "MEDIUM"
        return "LOW"

_calibrator: QuantileCalibrator | None = None

def calibrator() -> QuantileCalibrator:
    global _calibrator
    if _calibrator is None:
        _calibrator = QuantileCalibrator()
    return _calibrator

__all__ = ["calibrator", "QuantileCalibrator"]
