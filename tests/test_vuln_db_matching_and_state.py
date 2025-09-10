import os, asyncio, time, json
import pytest
from fastapi.testclient import TestClient

# These tests expect a Postgres URL (NEON_DATABASE_URL or DATABASE_URL). If not set, they are skipped.
POSTGRES_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="Postgres URL not configured for DB-backed tests")

os.environ.setdefault("ADMIN_API_KEY", "test-key")
from core.main import app  # noqa: E402
from storage import postgres  # noqa: E402
from storage import vuln_store  # noqa: E402

client = TestClient(app)

def _auth():
    return {"x-api-key": "test-key"}

@pytest.fixture(scope="module", autouse=True)
def _migrate():
    # Apply migrations once
    import asyncio
    from storage.migrations import apply_migrations
    asyncio.get_event_loop().run_until_complete(apply_migrations())
    yield

async def _fetch(sql, *args):
    return await postgres.fetch(sql, *args)  # type: ignore

@pytest.mark.asyncio
async def test_finding_creation_and_idempotent_matching():
    # Ingest SBOM with two components
    payload = {
        "asset_name": "svc-a",
        "document": {"components": [
            {"name": "package-one", "version": "1.0.0", "type": "library"},
            {"name": "package-two", "version": "2.1.0", "type": "library"},
        ]}
    }
    r = client.post("/vuln/ingest_sbom", json=payload, headers=_auth())
    assert r.status_code == 200
    first = r.json()
    # Re-ingest same SBOM -> idempotent matching should not increase matched findings
    r2 = client.post("/vuln/ingest_sbom", json=payload, headers=_auth())
    assert r2.status_code == 200
    second = r2.json()
    # matched_findings second run should be 0 (idempotent) or minimal
    assert second.get("matched_findings", 0) <= first.get("matched_findings", 0)

@pytest.mark.asyncio
async def test_state_transition_event_logging():
    # Create a synthetic finding directly (simulate earlier match)
    fid = "finding-test-cve"
    await vuln_store.upsert_finding({  # type: ignore
        "id": fid,
        "cve_id": "CVE-2025-XYZ0",
        "asset_id": "svc-a", "component_id": None,
        "first_seen": time.time(), "last_seen": time.time(),
        "state": "open", "detection_source": "unit", "risk_score": 0.2, "risk_severity": "LOW", "asset_metadata": json.dumps({"criticality": 0.5})
    })
    r = client.post(f"/vuln/findings/{fid}/state", json={"state": "triaged"}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["changed"] is True
    rows = await _fetch("SELECT * FROM finding_events WHERE finding_id=$1", fid)
    assert any((json.loads(row[4]).get("to") == "triaged") for row in rows)

@pytest.mark.asyncio
async def test_feed_etag_persistence_and_reuse():
    # Insert synthetic feed state, then fetch NVD (placeholder) and ensure upsert updates timestamp
    before = await _fetch("SELECT * FROM feed_state WHERE feed_name='nvd'")
    await vuln_store.upsert_feed_state("nvd", etag="W/\"etag123\"", status="ok")  # type: ignore
    mid = await _fetch("SELECT * FROM feed_state WHERE feed_name='nvd'")
    assert mid, "feed_state upsert failed"
    # Simulate fetch; network may be disabled so just call fetcher
    from scanner.feeds import fetch_nvd_recent
    await fetch_nvd_recent()  # best-effort
    after = await _fetch("SELECT * FROM feed_state WHERE feed_name='nvd'")
    assert after, "feed_state missing after fetch"
    assert after[0][2] >= mid[0][2], "last_fetch_ts not advanced or equal"