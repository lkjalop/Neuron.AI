"""Shared evaluation utilities for model/detector comparison.

Provides:
  - load_labeled_events(path): yields Event objects ensuring label presence
  - compute_confusion(preds, truths)
  - metric_dict(tp, fp, fn)
  - bootstrap_ci(samples, n_resamples, alpha)
  - utility_score(precision, recall, fp_rate, w_p, w_r, w_fp)
  - mcnemar(baseline_preds, candidate_preds, truths)

Design Notes:
  - Functions are intentionally dependency-light (pure Python + stdlib only)
  - For bootstrap we resample indices with replacement.
  - McNemar: use exact binomial if small total (b + c <= 25) else chi-square approx.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any
import json, math, random

from core.event import dict_to_event, Event

RNG = random.Random()


def set_seed(seed: int | None):
    if seed is not None:
        RNG.seed(seed)


def load_labeled_events(path: Path) -> Iterable[Event]:
    with path.open(encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                raw = json.loads(s)
            except json.JSONDecodeError:
                continue
            try:
                ev = dict_to_event(raw)
            except Exception:
                continue
            yield ev


def compute_confusion(preds: List[int], truths: List[int]) -> Tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for p, t in zip(preds, truths):
        if p == 1 and t == 1:
            tp += 1
        elif p == 1 and t == 0:
            fp += 1
        elif p == 0 and t == 0:
            tn += 1
        elif p == 0 and t == 1:
            fn += 1
    return tp, fp, tn, fn


def metric_dict(tp: int, fp: int, tn: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "fp_rate": fp_rate,
    }


def bootstrap_ci(values: List[float], n_resamples: int = 1000, alpha: float = 0.05) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    n = len(values)
    res: List[float] = []
    for _ in range(n_resamples):
        sample = [values[RNG.randrange(0, n)] for _ in range(n)]
        res.append(sum(sample) / len(sample))
    res.sort()
    lower_idx = int((alpha / 2) * n_resamples)
    upper_idx = int((1 - alpha / 2) * n_resamples) - 1
    lower_idx = max(0, min(lower_idx, n_resamples - 1))
    upper_idx = max(0, min(upper_idx, n_resamples - 1))
    return res[lower_idx], res[upper_idx]


def utility_score(precision: float, recall: float, fp_rate: float, w_p: float, w_r: float, w_fp: float) -> float:
    return w_p * precision + w_r * recall - w_fp * fp_rate


def mcnemar(baseline_preds: List[int], candidate_preds: List[int], truths: List[int]) -> Dict[str, Any]:
    # b: baseline correct, candidate wrong; c: baseline wrong, candidate correct
    b = c = 0
    for b_p, c_p, t in zip(baseline_preds, candidate_preds, truths):
        b_correct = (b_p == t)
        c_correct = (c_p == t)
        if b_correct and not c_correct:
            b += 1
        elif c_correct and not b_correct:
            c += 1
    total = b + c
    if total == 0:
        return {"b": b, "c": c, "p_value": 1.0, "method": "degenerate"}
    # exact binomial (two-sided) if small
    if total <= 25:
        # two-sided p = 2 * sum_{i=0}^{min(b,c)} Binomial(total, 0.5) probability of i or less extreme
        # simplified: compute tail for min(b,c)
        k = min(b, c)
        prob = 0.0
        for i in range(0, k + 1):
            comb = math.comb(total, i)
            prob += comb * (0.5 ** total)
        p = min(1.0, 2 * prob)
        return {"b": b, "c": c, "p_value": p, "method": "exact"}
    # chi-square approximation with continuity correction
    diff = abs(b - c) - 1
    chi_sq = (diff * diff) / total if total else 0.0
    # p-value from chi-square with 1 df: use survival function approx
    # p ~ exp(-0.5 * chi_sq) * (1 + sqrt(chi_sq/2))  (rough upper bound) but we'll implement simple tail via math.erfc
    # For simplicity use normal approximation: z = diff / sqrt(total); p_two = 2*(1-Phi(|z|))
    z = (abs(b - c) - 1) / math.sqrt(total)
    # Phi(z) approx using error function
    phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    p_two = 2 * (1 - phi)
    p_two = max(0.0, min(1.0, p_two))
    return {"b": b, "c": c, "p_value": p_two, "method": "approx"}

__all__ = [
    "set_seed",
    "load_labeled_events",
    "compute_confusion",
    "metric_dict",
    "bootstrap_ci",
    "utility_score",
    "mcnemar",
]
