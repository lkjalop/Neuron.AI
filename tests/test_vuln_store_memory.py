import asyncio
import types
import pytest

# These tests operate in memory without a real Postgres DSN. We focus on endpoint fallbacks.
from fastapi.testclient import TestClient
from core.main import app


@pytest.fixture(scope="module")
def client():
    os_key = "ADMIN_API_KEY"
    import os
    os.environ[os_key] = "test-key"
    return TestClient(app)


def _auth_headers():
    return {"x-api-key": "test-key"}


def test_vuln_findings_empty_initial(client):
    r = client.get("/vuln/findings", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 0
    assert data["source"] in {"memory", "postgres"}


def test_vuln_vulnerabilities_empty_initial(client):
    r = client.get("/vuln/vulnerabilities", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 0
    assert data["source"] in {"memory", "postgres"}


def test_ingest_sbom_roundtrip(client):
    payload = {
        "asset_name": "demo-app",
        "document": {"components": [{"name": "libA", "version": "1.0.0", "type": "library"}]}
    }
    r = client.post("/vuln/ingest_sbom", json=payload, headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["components"][0]["name"] == "libA"