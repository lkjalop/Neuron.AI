"""Performance profiling harness for risk recompute with synthetic findings."""
from __future__ import annotations

import asyncio, time
from scanner.models import Vulnerability, Finding  # type: ignore
from scanner.scanner_agent import _VULNS, _FINDINGS, risk_recompute_all  # type: ignore
from storage import vuln_store  # type: ignore
from datetime import datetime, timezone


async def seed(n: int):
    now = datetime.now(timezone.utc)
    for i in range(n):
        cve = f"CVE-2025-{i:04d}"
        if cve not in _VULNS:
            v = Vulnerability(
                id=cve, cve_id=cve, source="seed", published_ts=now, modified_ts=now,
                severity="MEDIUM", cvss_base=5.0, cvss_vector="CVSS:3.1/...", aliases=[], cwe_ids=[],
                exploit_available=False, epss=0.1, kev_listed=False, raw_json={}
            )
            _VULNS[cve] = v
            await vuln_store.upsert_vulnerability(v)  # type: ignore[attr-defined]
        fid = f"finding-{cve}"
        if fid not in _FINDINGS:
            f = Finding(
                id=fid, tenant_id="global", vulnerability_id=cve, component_id="component-demo", asset_id=None,
                introduced_ts=now, detected_ts=now, status="open", status_reason=None,
                last_status_change_ts=now, sla_due_ts=None, risk_score=None, last_risk_calc_ts=None,
                meta={"criticality": 0.5},
            )
            _FINDINGS[fid] = f
            await vuln_store.upsert_finding({  # type: ignore[attr-defined]
                "id": fid, "cve_id": cve, "asset_id": None, "component_id": "component-demo",
                "first_seen": now.timestamp(), "last_seen": now.timestamp(), "state": "open",
                "detection_source": "seed", "risk_score": None, "risk_severity": None, "asset_metadata": {"criticality": 0.5},
            })

async def main():
    await seed(500)
    t0 = time.time()
    await risk_recompute_all()
    dt = time.time() - t0
    print(f"Recompute for 500 findings took {dt:.3f}s -> {(500/dt):.1f} findings/sec")

if __name__ == "__main__":
    asyncio.run(main())
