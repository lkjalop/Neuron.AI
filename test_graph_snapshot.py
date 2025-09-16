import asyncio
import json
from fastapi.testclient import TestClient

from core.app_factory import create_app
from src.graph.relationships import get_graph


def _seed_graph():
    g = get_graph()

    async def _ops():
        await g.link_domain_asset("example.org", "srv1")
        await g.link_domain_asset("example.net", "srv2")
        await g.link_identity_asset("bob", "srv1")
        await g.link_identity_asset("bob", "srv2")
        await g.link_identity_finding("bob", "finding-1")
        await g.link_ioc_finding("fe:dc:ab:12", "finding-1", ioc_type="hash")
    asyncio.get_event_loop().run_until_complete(_ops())


def test_graph_snapshot_and_link_predict():
    app = create_app()
    client = TestClient(app)
    _seed_graph()

    # Manually refresh features to ensure presence
    resp = client.post("/api/v1/graph/refresh-features")
    assert resp.status_code == 200
    snap = client.get("/api/v1/graph/snapshot").json()
    assert "nodes" in snap and "edges" in snap
    assert "features" in snap and len(snap["features"]) >= 1
    # Check one node feature sample has degree fields
    any_feat = next(iter(snap["features"].values()))
    assert "degree_total" in any_feat

    # Link prediction for identity:bob should return some predictions (may be empty if fully connected)
    lp = client.get("/api/v1/graph/link-predict", params={"node_id": "identity:bob", "k": 3}).json()
    assert lp["node"] == "identity:bob"
    assert "predictions" in lp
    assert "candidate_space" in lp
