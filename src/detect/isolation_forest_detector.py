"""Isolation Forest detector integration.

Gated by environment variable EXPERIMENTAL_ISOFOREST=true
Retrains after configured batch size (default 500 events) to adapt distribution.
Uses only numeric features from Event.features (floats/ints) sorted by key for stable ordering.
"""
from __future__ import annotations
import os, time
from typing import List, Optional
from dataclasses import dataclass

from sklearn.ensemble import IsolationForest  # type: ignore

from core.event import Event
from core import metrics
from .orchestrator import Anomaly, Detector


def _env_enabled() -> bool:
    return os.environ.get("EXPERIMENTAL_ISOFOREST", "false").lower() in {"1", "true", "yes", "on"}


@dataclass
class IsolationForestConfig:
    retrain_interval: int = 500
    contamination: float = 0.01
    random_state: int = 42
    max_samples: str | int = "auto"


class IsolationForestDetector(Detector):
    name = "iforest"
    cost_hint = 0.4  # after baseline

    def __init__(self, config: Optional[IsolationForestConfig] = None):
        if not _env_enabled():  # Hard gate to avoid accidental load
            raise RuntimeError("IsolationForestDetector enabled only when EXPERIMENTAL_ISOFOREST=true")
        self.config = config or IsolationForestConfig()
        self.model: Optional[IsolationForest] = None
        self.buffer: List[list[float]] = []
        self.feature_keys: List[str] = []  # stable ordering
        self._since_retrain = 0

    def _extract_features(self, event: Event) -> Optional[list[float]]:
        if not event.features:
            return None
        numeric = {k: v for k, v in event.features.items() if isinstance(v, (int, float))}
        if not numeric:
            return None
        if not self.feature_keys:
            self.feature_keys = sorted(numeric.keys())
        # If keys have changed, ignore event until stable (simple strategy)
        if set(self.feature_keys) != set(numeric.keys()):
            return None
        return [float(numeric[k]) for k in self.feature_keys]

    def evaluate(self, event: Event) -> List[Anomaly]:
        vec = self._extract_features(event)
        if vec is None:
            return []
        self.buffer.append(vec)
        self._since_retrain += 1
        tenant = event.tenant_id or 'global'
        anomalies: List[Anomaly] = []
        # Train lazily when enough samples collected
        if self.model is None and len(self.buffer) >= max(50, len(self.feature_keys) * 10):
            self._train(tenant)
            self._since_retrain = 0
        # Periodic retrain
        if self.model and self._since_retrain >= self.config.retrain_interval:
            self._train(tenant)
            self._since_retrain = 0
        if self.model:
            try:
                pred = self.model.predict([vec])[0]  # -1 anomaly, 1 normal
                score = -self.model.score_samples([vec])[0]  # higher -> more anomalous
            except Exception:
                return []
            if pred == -1:
                anomalies.append(Anomaly(
                    event_id=event.event_id,
                    detector=self.name,
                    score=float(score),
                    reason=f"iforest_score={score:.3f}",
                    ts=time.time(),
                    tenant_id=event.tenant_id,
                    meta={"features": len(vec)},
                ))
        return anomalies

    def _train(self, tenant: str):
        try:
            self.model = IsolationForest(
                contamination=self.config.contamination,
                random_state=self.config.random_state,
                max_samples=self.config.max_samples,
                n_estimators=100,
            )
            self.model.fit(self.buffer)
            metrics.IFOREST_RETRAINS_TOTAL.labels(tenant=tenant).inc()
        except Exception:
            pass

    def flush(self):  # no-op
        return None


__all__ = ["IsolationForestDetector", "IsolationForestConfig"]
