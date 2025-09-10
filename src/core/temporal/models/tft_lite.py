from __future__ import annotations

from typing import List, Tuple
import math, random

class TFTLite:
    """Deterministic lightweight temporal encoder (prototype).

    Not a full Temporal Fusion Transformer: provides
    - Positional encoding (sin/cos)
    - Single multi-head-like projection (fixed heads simulated)
    - Feed-forward collapse to predicted next vector

    Deterministic weights (seeded) for reproducibility and audit.
    """
    def __init__(self, window: int, feature_dim: int, seed: int = 42):
        self.window = window
        self.feature_dim = feature_dim
        rnd = random.Random(seed)
        # Simple linear projection weights: W1: F -> H, H = 2*F
        self.H = feature_dim * 2
        self.W1 = [[(rnd.random()*2-1)/feature_dim for _ in range(feature_dim)] for _ in range(self.H)]
        self.W2 = [[(rnd.random()*2-1)/self.H for _ in range(self.H)] for _ in range(feature_dim)]

    def _pos_enc(self) -> List[List[float]]:
        enc = []
        for t in range(self.window):
            row = []
            for i in range(self.feature_dim):
                pos = t / max(1, self.window-1)
                row.append(math.sin(pos * (i+1)))
            enc.append(row)
        return enc

    def forward(self, window_vecs: List[Tuple[float, ...]]) -> Tuple[List[float], List[float]]:
        if len(window_vecs) != self.window:
            # pad or truncate deterministically
            if len(window_vecs) < self.window:
                last = window_vecs[-1] if window_vecs else tuple(0.0 for _ in range(self.feature_dim))
                window_vecs = list(window_vecs) + [last] * (self.window - len(window_vecs))
            else:
                window_vecs = window_vecs[-self.window:]
        pe = self._pos_enc()
        # Combine inputs + positional
        combined = []
        for t in range(self.window):
            base = list(window_vecs[t])
            for i in range(self.feature_dim):
                base[i] = (base[i] + pe[t][i]) / 2.0
            combined.append(base)
        # Temporal aggregation: mean over time
        agg = [sum(combined[t][i] for t in range(self.window))/self.window for i in range(self.feature_dim)]
        # Project to hidden
        hidden = []
        for h in range(self.H):
            hidden.append(sum(self.W1[h][j]*agg[j] for j in range(self.feature_dim)))
        # GELU-ish activation
        hidden = [0.5*x*(1+math.tanh(math.sqrt(2/math.pi)*(x+0.044715*pow(x,3)))) for x in hidden]
        # Project back to feature space (prediction)
        pred = []
        for f in range(self.feature_dim):
            pred.append(sum(self.W2[f][h]*hidden[h] for h in range(self.H)))
        # Residual vector vs last actual window vector
        last_vec = list(window_vecs[-1])
        residual = [last_vec[i] - pred[i] for i in range(self.feature_dim)]
        return pred, residual

__all__ = ["TFTLite"]
