import json, time
import pytest
from fastapi.testclient import TestClient

from core.main import app, runtime_params

@pytest.fixture(scope="module")
def client():
    # Configure API keys for both scopes
    import os
    os.environ["ADMIN_API_KEY"] = "adminkey"
    os.environ["PREDICT_API_KEY"] = "predictkey"
    return TestClient(app)

@pytest.mark.asyncio
async def test_sla_upcoming_empty(client):
    r = client.get("/findings/sla/upcoming", headers={"x-api-key": "predictkey"})
    assert r.status_code in (200, 503)  # 503 if persistence not wired in test env
    if r.status_code == 200:
        body = r.json()
        assert "count" in body and "window_days" in body

def test_ioc_ingest_and_search(client):
    r = client.post("/ioc", json={"type": "domain", "value": "example.com"}, headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    r2 = client.get("/ioc/search?value=example", headers={"x-api-key": "adminkey"})
    assert r2.status_code == 200
    js = r2.json()
    assert js["count"] >= 1

@pytest.mark.asyncio
async def test_hunt_query_flow(client):
    # Push an event through /ingest so it lands in hunting buffer
    ev = {"event_id": "e1", "tenant_id": "t1", "message": "error connecting to example.com"}
    r_ing = client.post("/ingest", json=ev)
    assert r_ing.status_code == 200
    # Query hunting buffer
    r = client.post("/hunt/query", json={"pattern": "error"}, headers={"x-api-key": "adminkey"})
    assert r.status_code == 200
    js = r.json()
    assert js["count"] >= 1

@pytest.mark.asyncio
async def test_ticket_batching_no_findings(client):
    r = client.post("/tickets/remediation", json={}, headers={"x-api-key": "predictkey"})
    # If no persistence layer set up, may be 503; else 200 with empty tickets
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.json()
        assert body["total_tickets"] >= 0

