"""Qualys vulnerability scan connector skeleton.

Batch 1 scope:
- Provide async client stub (no real API calls yet) with pluggable auth.
- Normalization of raw (synthetic) Qualys-like findings into internal canonical dicts.
- Yield records via an async generator to integrate with ingestion later.

Future (outside Batch 1):
- Real HTTPS calls, pagination, delta windowing, retry / backoff, error taxonomy.
- Asset/vuln mapping enrichment & caching.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, List, Optional
import asyncio
import random
import time


@dataclass
class QualysConfig:
    base_url: str = "https://qualys.example/api"  # placeholder
    username: Optional[str] = None
    password: Optional[str] = None
    api_token: Optional[str] = None
    tenant_id: Optional[str] = None
    synthetic_mode: bool = True  # Batch 1: always synthetic
    batch_size: int = 50


@dataclass
class RawQualysFinding:
    qid: str
    host_identifier: str
    severity: int
    title: str
    cve_ids: List[str]
    first_found: float
    last_found: float
    patch_available: bool
    exploitability: Optional[str] = None


def _severity_to_score(severity: int) -> float:
    # Placeholder mapping (Qualys severity 1-5) -> internal 0-100 scale
    return {1: 10.0, 2: 30.0, 3: 55.0, 4: 75.0, 5: 90.0}.get(severity, 0.0)


def normalize_finding(raw: RawQualysFinding, tenant_id: str) -> Dict[str, Any]:
    """Convert RawQualysFinding into internal canonical vulnerability + finding event structure.

    For Batch 1 we output a flattened dict (later could split asset/vuln/finding tables).
    """
    vuln_id = f"qualys:{raw.qid}"
    return {
        "tenant_id": tenant_id,
        "event_type": "vuln_finding",
        "source": "qualys.synthetic" if raw.qid.startswith("SYNTH") else "qualys",
        "timestamp": raw.last_found,
        "severity": _severity_to_score(raw.severity),
        "metadata": {
            "qid": raw.qid,
            "host": raw.host_identifier,
            "title": raw.title,
            "cve_ids": raw.cve_ids,
            "first_found": raw.first_found,
            "last_found": raw.last_found,
            "patch_available": raw.patch_available,
            "exploitability": raw.exploitability,
            "vuln_id": vuln_id,
        },
        "features": {
            "severity_numeric": raw.severity,
            "cve_count": len(raw.cve_ids),
            "patch_available": 1 if raw.patch_available else 0,
        },
        "labels": {},
    }


class QualysClient:
    def __init__(self, config: QualysConfig):
        self.config = config

    async def fetch_findings(self) -> AsyncIterator[List[RawQualysFinding]]:
        """Synthetic generator returning batches of RawQualysFinding.

        Later this will page through real Qualys APIs.
        """
        # Batch 1: generate a finite sequence each call (e.g., 3 batches)
        batches = 3
        for _ in range(batches):
            await asyncio.sleep(0)  # allow event loop switch
            yield [self._random_finding() for _ in range(self.config.batch_size)]

    def _random_finding(self) -> RawQualysFinding:
        qid = f"SYNTH-{random.randint(1000, 9999)}"
        now = time.time()
        first = now - random.randint(0, 86400 * 30)
        last = now - random.randint(0, 3600)
        sev = random.choices([1, 2, 3, 4, 5], weights=[5, 15, 40, 25, 15])[0]
        cve_pool = [f"CVE-2024-{random.randint(1000,9999)}" for _ in range(random.randint(0, 3))]
        return RawQualysFinding(
            qid=qid,
            host_identifier=f"host-{random.randint(1,50)}",
            severity=sev,
            title=f"Synthetic Qualys Finding {qid}",
            cve_ids=cve_pool,
            first_found=min(first, last),
            last_found=max(first, last),
            patch_available=random.random() < 0.3,
            exploitability=random.choice([None, "POC", "ACTIVE_EXPLOIT"]) if random.random() < 0.2 else None,
        )


async def qualys_stream(config: QualysConfig) -> AsyncIterator[Dict[str, Any]]:
    """High-level async stream emitting normalized internal event dicts."""
    client = QualysClient(config)
    tenant_id = config.tenant_id or "default"
    async for batch in client.fetch_findings():
        for raw in batch:
            yield normalize_finding(raw, tenant_id)


__all__ = [
    "QualysConfig",
    "RawQualysFinding",
    "normalize_finding",
    "QualysClient",
    "qualys_stream",
]
