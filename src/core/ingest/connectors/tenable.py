"""Tenable (Nessus) vulnerability scan connector skeleton.

Parallels Qualys connector for consistency. Synthetic only in Batch 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, List, Optional
import asyncio, random, time


@dataclass
class TenableConfig:
    base_url: str = "https://tenable.example/api"
    api_key: Optional[str] = None
    tenant_id: Optional[str] = None
    synthetic_mode: bool = True
    batch_size: int = 40


@dataclass
class RawTenableFinding:
    plugin_id: str
    asset: str
    severity: int  # 0-4 Tenable severity scale
    name: str
    cve_ids: List[str]
    first_seen: float
    last_seen: float
    exploit_available: bool


def _tn_sev_to_score(sev: int) -> float:
    return {0: 5.0, 1: 20.0, 2: 45.0, 3: 70.0, 4: 90.0}.get(sev, 0.0)


def normalize_tenable(raw: RawTenableFinding, tenant_id: str) -> Dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "event_type": "vuln_finding",
        "source": "tenable.synthetic" if raw.plugin_id.startswith("SYNTH") else "tenable",
        "timestamp": raw.last_seen,
        "severity": _tn_sev_to_score(raw.severity),
        "metadata": {
            "plugin_id": raw.plugin_id,
            "asset": raw.asset,
            "cve_ids": raw.cve_ids,
            "first_seen": raw.first_seen,
            "last_seen": raw.last_seen,
            "exploit_available": raw.exploit_available,
        },
        "features": {
            "severity_numeric": raw.severity,
            "cve_count": len(raw.cve_ids),
            "exploit_available": 1 if raw.exploit_available else 0,
        },
        "labels": {},
    }


class TenableClient:
    def __init__(self, config: TenableConfig):
        self.config = config

    async def fetch_findings(self) -> AsyncIterator[List[RawTenableFinding]]:
        for _ in range(2):
            await asyncio.sleep(0)
            yield [self._random() for _ in range(self.config.batch_size)]

    def _random(self) -> RawTenableFinding:
        plugin = f"SYNTH-{random.randint(10000, 99999)}"
        now = time.time()
        first = now - random.randint(0, 86400 * 20)
        last = now - random.randint(0, 1800)
        sev = random.choices([0,1,2,3,4], weights=[2,10,40,30,18])[0]
        cves = [f"CVE-2024-{random.randint(1000,9999)}" for _ in range(random.randint(0, 2))]
        return RawTenableFinding(
            plugin_id=plugin,
            asset=f"asset-{random.randint(1,60)}",
            severity=sev,
            name=f"Synthetic Tenable Finding {plugin}",
            cve_ids=cves,
            first_seen=min(first, last),
            last_seen=max(first, last),
            exploit_available=random.random() < 0.25,
        )


async def tenable_stream(config: TenableConfig) -> AsyncIterator[Dict[str, Any]]:
    client = TenableClient(config)
    tenant_id = config.tenant_id or "default"
    async for batch in client.fetch_findings():
        for raw in batch:
            yield normalize_tenable(raw, tenant_id)


__all__ = [
    "TenableConfig",
    "RawTenableFinding",
    "normalize_tenable",
    "TenableClient",
    "tenable_stream",
]
