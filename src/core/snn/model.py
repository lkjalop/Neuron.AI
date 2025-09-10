"""SNN abstraction module.

Provides backend selector for proto, lif (future), and multi-layer placeholders.
The detector will import this instead of directly binding to prototype classes.
"""
from __future__ import annotations
from typing import List
import math
from dataclasses import dataclass

try:
    from config import runtime_params
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

class SNNBackend:
    def forward(self, spikes: List[List[int]]) -> float:  # noqa: D401
        raise NotImplementedError

class ProtoBackend(SNNBackend):
    def __init__(self, decay: float):
        self.decay = float(decay)
    def forward(self, spikes: List[List[int]]) -> float:
        v = 0.0
        for step in spikes:
            v = v * self.decay + sum(step)
        return v

class MultiLayerProtoBackend(SNNBackend):
    """Placeholder multi-layer accumulation using successive tanh compressions."""
    def __init__(self, layers: int, decay: float):
        self.layers = max(1, layers)
        self.decay = float(decay)
    def forward(self, spikes: List[List[int]]) -> float:
        acc = 0.0
        for step in spikes:
            s = sum(step)
            acc = acc * self.decay + s
            # layer transforms
            tmp = acc
            for _ in range(self.layers - 1):
                tmp = math.tanh(tmp)
            acc = tmp
        return acc

try:
    import snntorch as _snn  # type: ignore
    import torch as _torch  # type: ignore
except Exception:  # pragma: no cover
    _snn = None  # type: ignore
    _torch = None  # type: ignore

class LIFBackend(SNNBackend):
    def __init__(self, hidden_size: int, decay: float):
        if _snn is None or _torch is None:
            raise RuntimeError("snntorch/torch not available")
        self.hidden = hidden_size
        self.decay = decay
        self.lif = _snn.Leaky(beta=decay)
    def forward(self, spikes: List[List[int]]) -> float:  # pragma: no cover (heavy path optional)
        if not spikes:
            return 0.0
        T = len(spikes); F = len(spikes[0]) if T else 0
        x = _torch.tensor(spikes, dtype=_torch.float32)
        W = _torch.ones((F, self.hidden), dtype=_torch.float32) / max(1, F)
        h = x @ W
        mem = _torch.zeros(self.hidden)
        last = 0.0
        for t in range(T):
            spk, mem = self.lif(h[t], mem)
            last = float(mem.mean().item())
        return last

@dataclass
class BackendConfig:
    mode: str = "proto"  # proto | proto_multi | lif
    decay: float = 0.95
    hidden_size: int = 32
    layers: int = 2


def build_backend() -> SNNBackend:
    mode = "proto"
    decay = 0.95
    hidden = 32
    layers = 2
    try:
        if runtime_params:
            mode = str(runtime_params.get_param("snn.mode") or mode)
            decay = float(runtime_params.get_param("snn.lif_decay") or decay)
            hidden = int(runtime_params.get_param("snn.lif.hidden_size") or hidden)
            layers = int(runtime_params.get_param("snn.lif.layers") or 2) if hasattr(runtime_params, 'get_param') else 2
    except Exception:
        pass
    if mode == "lif":
        try:
            return LIFBackend(hidden_size=hidden, decay=decay)
        except Exception:
            return ProtoBackend(decay)
    if mode == "proto_multi":
        return MultiLayerProtoBackend(layers=layers, decay=decay)
    return ProtoBackend(decay)

__all__ = ["build_backend", "BackendConfig", "SNNBackend", "ProtoBackend", "MultiLayerProtoBackend", "LIFBackend"]
