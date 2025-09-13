from fastapi.testclient import TestClient


def test_readiness_degraded_with_partial_flag(monkeypatch):
    # Ensure required envs are not set except the partial readiness flag
    monkeypatch.delenv("PREDICT_API_KEY", raising=False)
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("GRAFANA_BASE_URL", raising=False)
    monkeypatch.setenv("ALLOW_PARTIAL_READINESS", "1")
    from core.main import app
    with TestClient(app) as client:
        r = client.get("/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "degraded"
        assert body.get("mode") == "partial"
        assert isinstance(body.get("missing"), list) and body.get("missing")
