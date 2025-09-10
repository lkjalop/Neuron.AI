import os, json
from fastapi.testclient import TestClient

# Force low threshold & delta for deterministic adjustment
os.environ.setdefault("RETRIEVAL_TENANT_PARTITION", "false")
from config import runtime_params  # type: ignore
from src.core.main import app  # noqa: E402

client = TestClient(app)

def test_rag_drift_adjust_temporal_weight_decreases():
    # Seed runtime params
    try:
        runtime_params.update_param("retrieval.drift.added_ratio_threshold", 0.2, "test", actor="test")
        runtime_params.update_param("retrieval.drift.adjust.delta", 0.15, "test", actor="test")
        runtime_params.update_param("fusion.weight.temporal", 0.8, "test", actor="test")
    except Exception:
        pass
    docs = [
        {"id": f"d{i}", "text": f"content {i}"} for i in range(5)
    ]
    r1 = client.post("/rag/sync", json={"tenant": "t_test", "documents": docs})
    assert r1.status_code == 200, r1.text
    # Modify most documents to trigger high added/updated ratio
    docs2 = [
        {"id": f"d{i}", "text": f"content {i} updated"} for i in range(5)
    ] + [{"id": "d_new", "text": "new doc"}]
    prev_weight = runtime_params.get_param("fusion.weight.temporal")
    r2 = client.post("/rag/sync", json={"tenant": "t_test", "documents": docs2})
    assert r2.status_code == 200, r2.text
    new_weight = runtime_params.get_param("fusion.weight.temporal")
    # Weight should decrease by approx delta (allow small float tolerance)
    assert new_weight <= prev_weight - 0.14

