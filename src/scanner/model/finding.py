from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

_CANONICAL_FINDING_FIELDS = [
    "id", "plugin", "title", "severity", "exploitability", "score", "resources", "evidence", "tags", "fingerprint"
]

def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

@dataclass
class Finding:
    id: str
    plugin: str
    title: str
    severity: str  # e.g., LOW/MEDIUM/HIGH/CRITICAL
    exploitability: float  # 0..1 heuristic
    score: float  # blended risk score (exploitability * impact weight etc.)
    resources: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    fingerprint: Optional[str] = None  # deterministic hash for dedupe
    asset_metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        core = {
            k: getattr(self, k) for k in [
                "plugin", "title", "severity", "exploitability", "resources", "tags"
            ]
        }
        # evidence left out except stable keys to avoid noise; include selected keys if small
        ev = self.evidence
        if isinstance(ev, dict):
            stable_ev = {k: ev[k] for k in sorted(ev.keys()) if isinstance(ev[k], (str, int, float, bool))}
        else:
            stable_ev = {}
        payload = {"core": core, "evidence": stable_ev}
        h = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]
        self.fingerprint = h
        return h

    def to_dict(self) -> Dict[str, Any]:
        if not self.fingerprint:
            self.compute_fingerprint()
        data = asdict(self)
        # enforce canonical field ordering when serialized (helpful for tests / audits)
        ordered = {k: data.get(k) for k in _CANONICAL_FINDING_FIELDS}
        return ordered

    @classmethod
    def from_raw(cls, **kwargs) -> "Finding":
        f = cls(**kwargs)
        f.compute_fingerprint()
        return f
