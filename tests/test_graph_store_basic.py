from __future__ import annotations

import asyncio, os, pytest
from storage.graph_store import upsert_node, upsert_edge, get_node, neighbors, search_knowledge_articles, upsert_knowledge_article


pytestmark = pytest.mark.skipif(not os.getenv("NEON_DATABASE_URL"), reason="DB not configured for graph tests")


async def _roundtrip():
    await upsert_node("ka:test", "KNOWLEDGE_ARTICLE", {"title": "Test Article", "body": "Body"})
    await upsert_node("vuln:CVE-2024-1234", "VULNERABILITY", {"cve_id": "CVE-2024-1234"})
    await upsert_edge("ka:test", "vuln:CVE-2024-1234", "RELATES_TO", {"reason": "mentions"})
    n = await get_node("ka:test")
    assert n is not None
    neigh = await neighbors("ka:test", direction="out")
    assert any(r["neighbor_id"].startswith("vuln:") for r in neigh)
    await upsert_knowledge_article("another", "Another Title", "Some body text")
    res = await search_knowledge_articles("another")
    assert res and any(r["title"].lower().startswith("another") for r in res)


def test_graph_store_roundtrip():
    asyncio.run(_roundtrip())
