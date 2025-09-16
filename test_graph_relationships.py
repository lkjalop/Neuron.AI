import asyncio

from src.graph.relationships import get_graph


def test_new_relationship_edges_creation():
    g = get_graph()

    async def _build():
        await g.link_domain_asset("example.com", "web01")
        await g.link_identity_asset("alice", "web01", auth_method="ssh")
        await g.link_identity_finding("alice", "f-123", role="initiator")
        await g.link_ioc_finding("1.2.3.4", "f-123", ioc_type="ip")

    asyncio.get_event_loop().run_until_complete(_build())

    export = g.export()
    type_counts = export.get("edge_type_counts", {})
    # Ensure each new edge type appears exactly once in this controlled test
    assert type_counts.get("resolves_to") == 1
    assert type_counts.get("authenticates_to") == 1
    assert type_counts.get("implicated_in") == 1
    assert type_counts.get("indicator_of") == 1

    # Spot-check path existence (identity -> asset via authenticates_to)
    assert g.path_exists("identity:alice", "asset:web01")
    # ioc to finding should exist directly
    assert g.path_exists("ioc:1.2.3.4", "finding:f-123")
