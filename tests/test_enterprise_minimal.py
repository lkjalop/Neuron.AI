import os
import sys
from fastapi.testclient import TestClient


def _get_client():
    from src.core.main import app
    return TestClient(app)


def test_professional_report_pdf():
    with _get_client() as client:
        r = client.get("/enterprise/report/professional")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct.lower()


def test_agents_health_has_planner():
    with _get_client() as client:
        r = client.get("/agents/health")
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j.get("agents"), list)
        # planner agent is registered during lifespan startup (best-effort)
        names = {a.get("name") for a in j.get("agents", [])}
        roles = {a.get("role") for a in j.get("agents", [])}
        assert ("planner" in names) or ("planner" in roles)


def test_control_intelligence_fallback():
    # Force fallback by disabling dump CompleteDatabaseIntegration
    import src.core.main as main
    main.CompleteDatabaseIntegration = None  # type: ignore
    with _get_client() as client:
        r = client.get("/api/intelligence/control/A.5.1")
        assert r.status_code == 200
        j = r.json()
        assert j.get("source") == "kg_fallback"
        data = j.get("data") or {}
        assert data.get("control_id") == "A.5.1"
