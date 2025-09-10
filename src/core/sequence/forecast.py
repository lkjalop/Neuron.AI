from __future__ import annotations
from typing import List
import math

class TFTStubForecaster:
    """Minimal forecaster stub. Computes simple moving average prediction and residual.
    Acts as placeholder for future Temporal Fusion Transformer.
    """
    def __init__(self, min_points: int = 10):
        self.min_points = min_points

    def predict_residual(self, series: List[float]) -> float:
        if len(series) < self.min_points:
            return 0.0
        avg = sum(series[:-1]) / max(1, len(series)-1)
        last = series[-1]
        return float(last - avg)

__all__ = ["TFTStubForecaster"]
