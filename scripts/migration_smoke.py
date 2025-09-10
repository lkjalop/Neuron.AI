"""Migration & schema smoke test.

Usage (PowerShell):
  $env:NEON_DATABASE_URL="postgres://..."; python -m scripts.migration_smoke
"""
from __future__ import annotations

import asyncio
from storage.migrations import apply_migrations  # type: ignore
from storage import postgres  # type: ignore

TABLES = [
    "anomalies","calibration_quantiles","assets","sbom_components","asset_components","vulnerabilities","findings","finding_events",
    "exceptions","exception_events","feature_series","feed_state","attack_techniques","attack_software","vuln_software_map","software_technique_map",
    "remediation_plans","feed_confidence"
]

async def main():
    await apply_migrations()
    rows = await postgres.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    present = {r[0] for r in rows}
    missing = [t for t in TABLES if t not in present]
    print("Tables present:", len(present))
    if missing:
        print("Missing:", missing)
    else:
        print("All expected tables present ✔")

if __name__ == "__main__":
    asyncio.run(main())
