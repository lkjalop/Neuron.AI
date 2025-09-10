"""Reasoner Adapter (skeleton).

Unifies interface for external / pluggable reasoning or LLM-backed analysis
modules. Provides a minimal abstraction so higher layers can request
explanations, summaries, or structured assessments without binding to a
specific provider.

Contract (initial):
  ReasonerAdapter(provider: str)
    .summarize(text) -> str
    .classify(prompt, labels) -> {label: score}
    .explain_finding(finding_dict) -> str

Environment selection via runtime param `llm.provider` (noop|remote). No actual
remote calls are performed; remote is simulated for now to keep offline safety.
"""
from __future__ import annotations

from typing import List, Dict
import hashlib


class ReasonerAdapter:
    def __init__(self, provider: str = "noop"):
        self.provider = provider

    def summarize(self, text: str, max_len: int = 200) -> str:
        if self.provider == "noop":
            return text[:max_len]
        # Simulated remote summarization: hash-based stable truncation pattern
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        core = text.split(". ")[0][: max_len - 16]
        return f"{core}...[{h}]"

    def classify(self, prompt: str, labels: List[str]) -> Dict[str, float]:
        if not labels:
            return {}
        # Deterministic pseudo scores (normalize hash segments)
        scores = []
        for i, lab in enumerate(labels):
            h = hashlib.sha256(f"{prompt}|{lab}".encode("utf-8")).hexdigest()
            val = int(h[:4], 16) / 0xFFFF
            scores.append(val)
        total = sum(scores) or 1.0
        return {lab: s / total for lab, s in zip(labels, scores)}

    def explain_finding(self, finding: Dict) -> str:
        base = f"Finding {finding.get('id')} CVE={finding.get('cve_id')} severity={finding.get('risk_severity')} score={finding.get('risk_score')}"
        if self.provider == "noop":
            return base + " (noop explanation)"
        # Simulated reasoning chain stub
        return base + " | rationale: risk driven by multi-factor composite (simulated)"


__all__ = ["ReasonerAdapter"]