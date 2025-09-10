from __future__ import annotations

import asyncio
from typing import List

from core.ingest.connectors.qualys import QualysConfig, qualys_stream


async def _collect(n=10):
    cfg = QualysConfig(tenant_id="t1", batch_size=5)
    out = []
    async for ev in qualys_stream(cfg):
        out.append(ev)
        if len(out) >= n:
            break
    return out


def test_qualys_stream_basic():
    events = asyncio.run(_collect())
    assert events, "Should collect some events"
    e0 = events[0]
    assert e0["event_type"] == "vuln_finding"
    assert "metadata" in e0 and "qid" in e0["metadata"]
    assert "features" in e0 and "severity_numeric" in e0["features"]
