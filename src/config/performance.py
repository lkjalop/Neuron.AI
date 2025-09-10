"""Performance tier configuration (single source of truth).
Do not hardcode tier values elsewhere; import this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import os

TIERS: Dict[str, Dict[str, float]] = {
    # Granular tiers (5K -> 100K) for progressive scaling & pricing.
    "demo": {  # 5K
        "snn_neurons": 5_000,
        "events_per_second": 500,
        "detection_latency_ms": 180,
        "prediction_window_ms": 40,
        "gpu_memory_mb": 150,
        "cpu_cores": 1.0,
        "ram_gb": 2,
    },
    "starter": {  # 10K
        "snn_neurons": 10_000,
        "events_per_second": 1_000,
        "detection_latency_ms": 160,
        "prediction_window_ms": 50,
        "gpu_memory_mb": 250,
        "cpu_cores": 1.5,
        "ram_gb": 3,
    },
    "growth": {  # 15K
        "snn_neurons": 15_000,
        "events_per_second": 1_600,
        "detection_latency_ms": 150,
        "prediction_window_ms": 60,
        "gpu_memory_mb": 325,
        "cpu_cores": 2.0,
        "ram_gb": 4,
    },
    "pro": {  # 25K
        "snn_neurons": 25_000,
        "events_per_second": 2_500,
        "detection_latency_ms": 135,
        "prediction_window_ms": 70,
        "gpu_memory_mb": 450,
        "cpu_cores": 3.0,
        "ram_gb": 6,
    },
    "advanced": {  # 50K
        "snn_neurons": 50_000,
        "events_per_second": 5_000,
        "detection_latency_ms": 110,
        "prediction_window_ms": 85,
        "gpu_memory_mb": 900,
        "cpu_cores": 4.5,
        "ram_gb": 9,
    },
    "production": {  # 75K
        "snn_neurons": 75_000,
        "events_per_second": 7_500,
        "detection_latency_ms": 95,
        "prediction_window_ms": 100,
        "gpu_memory_mb": 1_500,
        "cpu_cores": 6.0,
        "ram_gb": 12,
    },
    "scale": {  # 100K
        "snn_neurons": 100_000,
        "events_per_second": 10_000,
        "detection_latency_ms": 80,
        "prediction_window_ms": 120,
        "gpu_memory_mb": 2_000,
        "cpu_cores": 8.0,
        "ram_gb": 16,
    },
}

DEFAULT_TIER = os.getenv("NEURONS_TIER", "validation").lower()
if DEFAULT_TIER not in TIERS:
    # Fallback gracefully in test / dev contexts instead of raising hard error
    DEFAULT_TIER = "demo"

@dataclass(frozen=True)
class TierConfig:
    name: str
    snn_neurons: int
    events_per_second: int
    detection_latency_ms: int
    prediction_window_ms: int
    gpu_memory_mb: int
    cpu_cores: float
    ram_gb: int

    @staticmethod
    def from_name(name: str) -> "TierConfig":
        d = TIERS[name]
        return TierConfig(
            name=name,
            snn_neurons=int(d["snn_neurons"]),
            events_per_second=int(d["events_per_second"]),
            detection_latency_ms=int(d["detection_latency_ms"]),
            prediction_window_ms=int(d["prediction_window_ms"]),
            gpu_memory_mb=int(d["gpu_memory_mb"]),
            cpu_cores=float(d["cpu_cores"]),
            ram_gb=int(d["ram_gb"]),
        )

ACTIVE_TIER = TierConfig.from_name(DEFAULT_TIER)

def switch_tier(name: str) -> TierConfig:
    """Switch the active tier (in-memory) and return new TierConfig.

    NOTE: Callers must perform any dependent subsystem reinitialization (e.g., SNN reservoir resize)
    after invoking this function. This function does not persist to env; it mutates module-level state.
    """
    global ACTIVE_TIER
    if name not in TIERS:
        raise ValueError(f"Unsupported tier '{name}'. Valid: {list(TIERS.keys())}")
    ACTIVE_TIER = TierConfig.from_name(name)
    return ACTIVE_TIER

__all__ = [
    "TIERS",
    "TierConfig",
    "ACTIVE_TIER",
    "switch_tier",
]
