"""Insights Engine

Transforms anomalies + recent context into human-consumable insights.
Current implementation is heuristic and lightweight.
"""
from __future__ import annotations

from typing import List, Dict, Any
import time

from detect.orchestrator import Anomaly


class Insight:
    def __init__(self, title: str, severity: float, detail: str, tags: Dict[str, Any]):
        self.title = title
        self.severity = severity
        self.detail = detail
        self.tags = tags
        self.ts = time.time()

    def to_dict(self):
        return {
            "title": self.title,
            "severity": self.severity,
            "detail": self.detail,
            "tags": self.tags,
            "ts": self.ts,
        }


class InsightsEngine:
    def __init__(self, burst_threshold: int = 3):
        self.burst_threshold = burst_threshold
        self._buffer: List[Anomaly] = []

    def ingest(self, anomalies: List[Anomaly]):
        if anomalies:
            self._buffer.extend(anomalies[-50:])  # cap growth heuristically
            if len(self._buffer) > 200:
                self._buffer = self._buffer[-200:]

    def generate(self) -> List[Insight]:
        if not self._buffer:
            return []
        # Group by event_id to find bursty multi-detector correlations
        by_event: Dict[str, List[Anomaly]] = {}
        for a in self._buffer:
            by_event.setdefault(a.event_id, []).append(a)
        insights: List[Insight] = []
        for eid, group in by_event.items():
            if len(group) >= self.burst_threshold:
                detectors = sorted({g.detector for g in group})
                max_score = max(g.score for g in group)
                insights.append(Insight(
                    title="Multi-detector corroborated anomaly",
                    severity=min(100.0, max_score * 10),
                    detail=f"Event {eid} flagged by {len(group)} detectors: {', '.join(detectors)}",
                    tags={"detectors": detectors, "event_id": eid},
                ))
        return insights

__all__ = ["InsightsEngine", "Insight"]
