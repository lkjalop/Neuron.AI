import os, json, asyncio
from fastapi.testclient import TestClient

# Ensure env toggle state for tests
ios_env_partition = os.getenv("RETRIEVAL_TENANT_PARTITION", "false")
os.environ["RETRIEVAL_TENANT_PARTITION"] = "true"

from src.core.main import app  # noqa: E402

client = TestClient(app)


def test_rag_sync_basic():
    docs = [
        {"id": "d1", "text": "hello world"},
        {"id": "d2", "text": "another doc"},
    ]
    r = client.post("/rag/sync", json={"tenant": "t1", "documents": docs})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["added"] == 2
    assert data["updated"] == 0
    # Re-run with one modified document
    docs2 = [
        {"id": "d1", "text": "hello world!!!"},  # updated
        {"id": "d2", "text": "another doc"},     # unchanged
        {"id": "d3", "text": "new third"},        # added
    ]
    r2 = client.post("/rag/sync", json={"tenant": "t1", "documents": docs2})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["added"] == 1
    assert d2["updated"] == 1
    assert d2["unchanged"] >= 1


def test_rag_sync_bad_payload():
    r = client.post("/rag/sync", json={"tenant": "t1", "documents": {"not": "a list"}})
    assert r.status_code == 400

# Restore env variable
os.environ["RETRIEVAL_TENANT_PARTITION"] = ios_env_partition
