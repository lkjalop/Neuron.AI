"""Lightweight forecasting module providing EWMA & Holt-Winters additive.

Produces residual = |actual - forecast| for integration into SNN activity.
"""
from __future__ import annotations
from typing import Optional, List
from config import runtime_params

class EWMAPredictor:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self._value: Optional[float] = None
    def update(self, x: float) -> float:
        if self._value is None:
            self._value = x
        else:
            self._value = self.alpha * x + (1 - self.alpha) * self._value
        return self._value

class HoltWintersAdditive:
    def __init__(self, alpha: float, beta: float, gamma: float, season_length: int = 0):
        self.alpha = alpha; self.beta = beta; self.gamma = gamma
        self.season_length = season_length if season_length > 1 else 0
        self.level: Optional[float] = None
        self.trend: float = 0.0
        self.season: List[float] = []
        self._idx = 0
    def update(self, x: float) -> float:
        if self.level is None:
            self.level = x
            if self.season_length:
                self.season = [0.0]*self.season_length
            return x
        prev_level = self.level
        if self.season_length:
            s = self.season[self._idx]
            self.level = self.alpha * (x - s) + (1 - self.alpha) * (self.level + self.trend)
            self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * self.trend
            self.season[self._idx] = self.gamma * (x - self.level) + (1 - self.gamma) * s
            fc = self.level + self.trend + self.season[self._idx]
            self._idx = (self._idx + 1) % self.season_length
            return fc
        # No seasonality
        self.level = self.alpha * x + (1 - self.alpha) * (self.level + self.trend)
        self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * self.trend
        return self.level + self.trend

class ResidualForecaster:
    def __init__(self):
        alpha = float(runtime_params.get_param("forecast.ewma.alpha") or 0.3)
        holt = bool(runtime_params.get_param("forecast.enable_holt_winters") or False)
        if holt:
            beta = float(runtime_params.get_param("forecast.holt.beta") or 0.1)
            gamma = float(runtime_params.get_param("forecast.holt.gamma") or 0.0)
            # Keep season length simple (optional future param)
            self._model = HoltWintersAdditive(alpha=alpha, beta=beta, gamma=gamma, season_length=0)
        else:
            self._model = EWMAPredictor(alpha)
    def residual(self, x: float) -> float:
        forecast = self._model.update(x)
        return abs(x - forecast)

__all__ = ["ResidualForecaster"]
