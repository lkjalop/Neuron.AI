"""SNN Repository Neuron Pool Management.

Provides a rotate() hook invoked by governance (diminishing returns service)
that simulates retirement of a subset of neurons and introduction of fresh
(randomized) neurons to attempt unique anomaly coverage uplift.

Design (scaffold):
- Internal state tracks a list of neuron descriptors (id, age, utility_score)
- rotate() selects lowest-utility decile (or min count) for replacement
- Replacement emits a summary dict for audit + returns stats
- Future: integrate real model weights or reservoir embeddings.

Runtime params:
  repository.rotation.replace_fraction (float 0..1, default 0.1)
  repository.rotation.min_replace (int, default 2)
  repository.rotation.neuron_pool_size (int, default 100)

Metrics updated externally (rotations counter & coverage uplift). This module focuses on state mutation.
"""
from __future__ import annotations
import random, time, threading
from typing import List, Dict, Any
from config import runtime_params

class _RepositoryState:
    def __init__(self):
        self._lock = threading.Lock()
        self.neurons: List[dict] = []
        self._init_pool()

    def _init_pool(self):
        size = 100
        try:
            v = runtime_params.get_param("repository.rotation.neuron_pool_size")
            if isinstance(v,(int,float)) and int(v) > 0:
                size = int(v)
        except Exception:
            pass
        now = time.time()
        self.neurons = [
            {"id": f"n{i}", "age_s": 0.0, "created": now, "utility": random.random()} for i in range(size)
        ]

    def rotate(self) -> Dict[str, Any]:
        """Perform a rotation replacing a fraction of lowest-utility neurons.
        Returns summary: {replaced: int, pool_size: int, avg_utility: float}
        """
        replace_fraction = 0.1
        min_replace = 2
        try:
            rf = runtime_params.get_param("repository.rotation.replace_fraction")
            if isinstance(rf,(int,float)) and 0 < float(rf) <= 1:
                replace_fraction = float(rf)
            mr = runtime_params.get_param("repository.rotation.min_replace")
            if isinstance(mr,(int,float)) and int(mr) >= 0:
                min_replace = int(mr)
        except Exception:
            pass
        with self._lock:
            size = len(self.neurons)
            if size == 0:
                self._init_pool()
                size = len(self.neurons)
            replace_count = max(min_replace, int(size * replace_fraction))
            replace_count = min(replace_count, size)
            # Sort by utility ascending
            self.neurons.sort(key=lambda x: x.get("utility",0.0))
            to_replace = self.neurons[:replace_count]
            survivors = self.neurons[replace_count:]
            now = time.time()
            # Create replacements with fresh random utility
            new_neurons = [
                {"id": f"n{int(now*1000)}_{i}", "age_s": 0.0, "created": now, "utility": random.random()} for i in range(replace_count)
            ]
            # Age survivors
            for n in survivors:
                n["age_s"] = now - n.get("created", now)
                # Decay or adjust utility slightly random walk
                n["utility"] = max(0.0, min(1.0, n.get("utility",0.0) * (0.95 + random.random()*0.1)))
            self.neurons = survivors + new_neurons
            avg_utility = sum(n.get("utility",0.0) for n in self.neurons)/len(self.neurons)
            summary = {
                "replaced": replace_count,
                "pool_size": len(self.neurons),
                "avg_utility": avg_utility,
            }
            return summary

_state: _RepositoryState | None = None

def repository_state() -> _RepositoryState:
    global _state
    if _state is None:
        _state = _RepositoryState()
    return _state


def rotate() -> Dict[str, Any]:
    return repository_state().rotate()

__all__ = ["rotate", "repository_state"]
