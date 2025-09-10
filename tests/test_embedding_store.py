from __future__ import annotations

import asyncio, os, pytest
from storage.embedding_store import upsert_embedding, get_embedding, semantic_search

pytestmark = pytest.mark.skipif(not os.getenv("NEON_DATABASE_URL"), reason="DB not configured for embedding tests")


async def _roundtrip():
    await upsert_embedding("node:test1", [0.1,0.2,0.3], "hash64")
    await upsert_embedding("node:test2", [0.1,0.2,0.30001], "hash64")
    v = await get_embedding("node:test1")
    assert v and len(v) == 3
    res = await semantic_search([0.1,0.2,0.3], limit=5)
    assert any(r[0] == "node:test1" for r in res)


def test_embedding_roundtrip():
    asyncio.run(_roundtrip())
