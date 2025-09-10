"""Hopfield Memory Scaffold.

Simplified associative memory supporting:
- Initialization with dimension & capacity
- Store pattern (binary / float vector) with optional normalization
- Associate(query) returning (reconstructed, similarity)

Used as detector: if (1 - similarity) > threshold, emit anomaly (or if similarity > high threshold indicating strong recall event under suspicious context—here we use residual approach).

Runtime params:
  hopfield.enabled (bool)
  hopfield.dim (int)
  hopfield.capacity (int)
  hopfield.residual.threshold (float) default 0.35
  hopfield.store.max (int) limit stored patterns

Metrics:
  HOPFIELD_ASSOCIATION_LATENCY_SECONDS
  HOPFIELD_RECALL_SCORE (last)
  HOPFIELD_UNIQUE_RATIO (updated externally by fusion instrumentation later)
"""
from __future__ import annotations
import time, math, threading, random, json, os
from typing import List
from config import runtime_params
from core import metrics

class HopfieldMemory:
    def __init__(self, dim: int = 64, capacity: int = 256, persist_path: str | None = None):
        self.dim = dim
        self.capacity = capacity
        self._patterns: List[List[float]] = []
        self._lock = threading.Lock()
        self._persist_path = persist_path or os.path.join("artifacts", "hopfield_patterns.jsonl")
        self._dirty = False
        # Load existing patterns best-effort
        self._load_existing()
        # Start background saver (lightweight) if enabled via runtime param (default on)
        try:
            en = runtime_params.get_param("hopfield.persistence.enabled")
            if en in {None, 1, True, "1", "true", "on"}:
                t = threading.Thread(target=self._autosave_loop, daemon=True)
                t.start()
        except Exception:
            pass

    def _maybe_resize(self):
        try:
            if runtime_params:
                d = runtime_params.get_param("hopfield.dim")
                c = runtime_params.get_param("hopfield.capacity")
                if isinstance(d, (int,float)) and int(d) != self.dim:
                    self.dim = int(d)
                    # Drop patterns (simplistic) when dimension changes
                    self._patterns.clear()
                if isinstance(c, (int,float)) and int(c) != self.capacity:
                    self.capacity = int(c)
                    if len(self._patterns) > self.capacity:
                        self._patterns = self._patterns[-self.capacity:]
        except Exception:
            pass

    def store(self, vec: List[float]):
        if len(vec) != self.dim:
            return
        with self._lock:
            if len(self._patterns) >= self.capacity:
                # FIFO rotation
                self._patterns.pop(0)
            self._patterns.append(vec[:])
            self._dirty = True

    def associate(self, query: List[float]):
        start = time.time()
        self._maybe_resize()
        if len(query) != self.dim:
            return query, 0.0
        with self._lock:
            if not self._patterns:
                # store seed
                self._patterns.append(query[:])
                return query, 1.0
            # Simple energy-min pseudo recall: choose stored pattern with max cosine similarity
            best = None
            best_sim = -1.0
            qn = _norm(query)
            for p in self._patterns:
                sim = _cosine(query, p, qn)
                if sim > best_sim:
                    best_sim = sim
                    best = p
            reconstructed = best[:] if best is not None else query
        try:
            metrics.HOPFIELD_ASSOCIATION_LATENCY_SECONDS.observe(time.time() - start)
        except Exception:
            pass
        return reconstructed, max(0.0, min(1.0, best_sim))

    def enabled(self) -> bool:
        try:
            v = runtime_params.get_param("hopfield.enabled")
            if v in {0, False, "0", "false"}:
                return False
        except Exception:
            pass
        return True

    # --- Persistence Support ---
    def _load_existing(self):
        try:
            path = self._persist_path
            if not path:
                return
            if not os.path.exists(path):
                return
            loaded: list[list[float]] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        vec = obj.get("vec") if isinstance(obj, dict) else None
                        if isinstance(vec, list) and all(isinstance(x,(int,float)) for x in vec) and len(vec)==self.dim:
                            loaded.append([float(x) for x in vec])
                    except Exception:
                        continue
            if loaded:
                with self._lock:
                    self._patterns = loaded[-self.capacity:]
        except Exception:
            pass

    def _autosave_loop(self):
        interval = 15.0
        try:
            v = runtime_params.get_param("hopfield.persistence.interval_s")
            if isinstance(v,(int,float)) and v>0:
                interval = float(v)
        except Exception:
            pass
        while True:
            try:
                time.sleep(interval)
                self._save_if_dirty()
            except Exception:
                # swallow and continue
                continue

    def _save_if_dirty(self):
        if not self._dirty:
            return
        path = self._persist_path
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Write atomic: write to temp then replace
            tmp = path + ".tmp"
            patterns_copy: list[list[float]]
            with self._lock:
                patterns_copy = self._patterns[-self.capacity:]
                self._dirty = False
            with open(tmp, "w", encoding="utf-8") as f:
                for vec in patterns_copy:
                    f.write(json.dumps({"vec": vec})+"\n")
            os.replace(tmp, path)
            # Optionally emit metric for pattern count
            try:
                metrics.HOPFIELD_PATTERN_COUNT.labels(dim=str(self.dim)).set(len(patterns_copy))  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            # Re-mark dirty for retry later
            self._dirty = True

    def flush(self):
        """Public flush to persist immediately."""
        try:
            self._save_if_dirty()
        except Exception:
            pass

# Utilities

def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x*x for x in v)) or 1.0

def _cosine(a: List[float], b: List[float], an: float | None = None) -> float:
    if an is None:
        an = _norm(a)
    bn = _norm(b)
    return sum(x*y for x,y in zip(a,b)) / (an*bn)

_instance: HopfieldMemory | None = None

def hopfield_instance() -> HopfieldMemory:
    global _instance
    if _instance is None:
        dim = 64
        cap = 256
        try:
            if runtime_params:
                d = runtime_params.get_param("hopfield.dim")
                c = runtime_params.get_param("hopfield.capacity")
                if isinstance(d,(int,float)):
                    dim = int(d)
                if isinstance(c,(int,float)):
                    cap = int(c)
        except Exception:
            pass
        # Determine persistence path (runtime override optional)
        persist_path = None
        try:
            pp = runtime_params.get_param("hopfield.persistence.path")
            if isinstance(pp,str) and pp.strip():
                persist_path = pp.strip()
        except Exception:
            persist_path = None
        _instance = HopfieldMemory(dim=dim, capacity=cap, persist_path=persist_path)
    return _instance

__all__ = ["HopfieldMemory", "hopfield_instance"]
