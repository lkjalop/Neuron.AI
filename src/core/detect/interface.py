"""Detector interface and registry."""
from __future__ import annotations

from typing import Protocol, List, Any, Dict, Optional
from core.event import Event


class DetectionResult(dict):
    """Structured detection result (extend dict for easy JSON serialization)."""
    pass


class IDetector(Protocol):
    name: str

    def process(self, event: Event) -> List[DetectionResult]:  # returns zero or more anomaly records
        ...


class DetectorRegistry:
    def __init__(self):
        self._detectors: Dict[str, IDetector] = {}

    def register(self, detector: IDetector):
        # Idempotent registration to support multiple Pipeline constructions in tests
        existing = self._detectors.get(detector.name)
        if existing is not None:
            # If same class/type keep original (avoid duplicate side effects)
            if type(existing) is type(detector):  # noqa: E721
                return existing
            # Different implementation with same name -> replace (explicit decision) for flexibility
        self._detectors[detector.name] = detector
        return detector

    def detectors(self):
        return list(self._detectors.values())

    # Backward compatibility: some tests expect registry.get_all()
    def get_all(self):  # pragma: no cover - simple alias
        return self.detectors()

    def get(self, name: str) -> Optional[IDetector]:
        return self._detectors.get(name)

    def _reset_for_tests(self):  # pragma: no cover (explicitly invoked in tests)
        """Clear registered detectors (TEST SUPPORT ONLY)."""
        self._detectors.clear()


registry = DetectorRegistry()

__all__ = ["IDetector", "DetectionResult", "registry"]
