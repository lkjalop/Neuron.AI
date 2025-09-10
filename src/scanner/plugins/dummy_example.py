from __future__ import annotations
from typing import Iterable, Dict, Any, List
from .base import ScannerPlugin, ScanContext
from ..model.finding import Finding

class DummyExposurePlugin(ScannerPlugin):
    key = "dummy_exposure"
    description = "Flags events whose value exceeds a threshold as exposure risk"

    def scan(self, items: Iterable[Dict[str, Any]], ctx: ScanContext) -> List[Finding]:
        threshold = ctx.params.get("scanner.dummy.threshold", 100)
        findings: List[Finding] = []
        for ev in items:
            val = ev.get("value")
            if isinstance(val, (int, float)) and val > threshold:
                sev = "HIGH" if val > threshold * 2 else "MEDIUM"
                exploitability = 0.4 if sev == "MEDIUM" else 0.7
                f = Finding.from_raw(
                    id=f"dummy:{ev.get('id', 'unknown')}",
                    plugin=self.key,
                    title=f"Value {val} exceeds threshold {threshold}",
                    severity=sev,
                    exploitability=exploitability,
                    score=exploitability * (2.0 if sev == "HIGH" else 1.0),
                    resources=[str(ev.get("id", "?"))],
                    evidence={"value": val, "threshold": threshold},
                    tags=["exposure", "dummy"],
                )
                findings.append(f)
        return findings
