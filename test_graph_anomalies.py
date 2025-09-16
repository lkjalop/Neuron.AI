from fastapi.testclient import TestClient
from core.app_factory import create_app
from src.graph.relationships import get_graph
import asyncio

def _seed():
    g = get_graph()
    async def _ops():
        # create several edges to influence degree/activity
        await g.link_domain_asset("alpha.example", "srv1")
        await g.link_domain_asset("beta.example", "srv2")
        await g.link_identity_asset("user1", "srv1")
        await g.link_identity_asset("user2", "srv2")
        await g.link_identity_finding("user1", "finding-x")
        await g.link_ioc_finding("deadbeef", "finding-x", ioc_type="hash")
    asyncio.get_event_loop().run_until_complete(_ops())

def test_graph_anomalies_endpoint():
    app = create_app()
    client = TestClient(app)
    _seed()
    # Ensure features & embeddings are present path (manual refresh)
    client.post("/api/v1/graph/refresh-features", headers={"X-Graph-Key": ""})
    # train embeddings to allow embedding_distance component (ignore failure silently)
    try:
        client.post("/api/v1/graph/train-embeddings", headers={"X-Graph-Key": ""})
    except Exception:
        pass
    r = client.get("/api/v1/graph/anomalies", headers={"X-Graph-Key": ""})
    assert r.status_code == 200
    data = r.json()
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)
    # Each anomaly record should have composite score
    if data["anomalies"]:
        rec = data["anomalies"][0]
        assert "composite" in rec