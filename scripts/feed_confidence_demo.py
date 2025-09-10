"""Adjust feed confidence and observe emergence probability shift."""
from __future__ import annotations

import asyncio
from enrichment.feed_confidence import set_feed_confidence  # type: ignore
from scanner.scanner_agent import risk_recompute_all  # type: ignore
from storage import vuln_store  # type: ignore

async def main():
    print("Setting NVD feed confidence to 0.6")
    await set_feed_confidence("nvd", 0.6)
    await risk_recompute_all()
    rows = await vuln_store.list_findings(limit=5)  # type: ignore[attr-defined]
    for r in rows:
        rf = r.get("risk_factors") or {}
        print(r.get("id"), "feed_confidence=", (rf or {}).get("feed_confidence"), "emergence_p=", (rf or {}).get("emergence_p"))

if __name__ == "__main__":
    asyncio.run(main())
