"""Synthetic vulnerability & finding ingest demo.

Populates in-memory scanner structures & persists sample rows; triggers risk recompute then
prints emergence-related factors via the emergence API logic (direct store read).
"""
from __future__ import annotations

import asyncio, time
from scanner.models import Vulnerability, Finding  # type: ignore
from scanner.scanner_agent import _VULNS, _FINDINGS, risk_recompute_all  # type: ignore
from storage import vuln_store  # type: ignore
from datetime import datetime, timezone


async def main():
    now = datetime.now(timezone.utc)
    # Create 3 synthetic vulns
    vulns = []
    for i in range(1,4):
        cve = f"CVE-2025-00{i:02d}"
        v = Vulnerability(
            id=cve,
            cve_id=cve,
            source="synthetic",
            published_ts=now,
            modified_ts=now,
            severity="HIGH" if i%2 else "MEDIUM",
            cvss_base=7.5,
            cvss_vector="CVSS:3.1/...",
            aliases=[],
            cwe_ids=[],
            exploit_available= i==1,
            epss=0.4 + i*0.1,
            kev_listed= i==1,
            raw_json={"synthetic": True}
        )
        vulns.append(v)
        _VULNS[cve] = v
        await vuln_store.upsert_vulnerability(v)  # type: ignore[attr-defined]
    # Create findings
    for v in vulns:
        fid = f"finding-{v.cve_id}"
        f = Finding(
            id=fid,
            tenant_id="global",
            vulnerability_id=v.cve_id,
            component_id="component-demo",
            asset_id=None,
            introduced_ts=now,
            detected_ts=now,
            status="open",
            status_reason=None,
            last_status_change_ts=now,
            sla_due_ts=None,
            risk_score=None,
            last_risk_calc_ts=None,
            meta={"criticality": 0.5},
        )
        _FINDINGS[fid] = f
        await vuln_store.upsert_finding({  # type: ignore[attr-defined]
            "id": fid,
            "cve_id": v.cve_id,
            "asset_id": None,
            "component_id": "component-demo",
            "first_seen": now.timestamp(),
            "last_seen": now.timestamp(),
            "state": "open",
            "detection_source": "synthetic",
            "risk_score": None,
            "risk_severity": None,
            "asset_metadata": {"criticality": 0.5},
        })
    await risk_recompute_all()
    rows = await vuln_store.list_findings(limit=10)  # type: ignore[attr-defined]
    print("Findings with predictive factors:")
    for r in rows:
        print(r.get("id"), r.get("risk_score"), (r.get("risk_factors") or {}).get("emergence_p"))

if __name__ == "__main__":
    asyncio.run(main())
