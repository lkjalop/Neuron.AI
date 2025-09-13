from fastapi.testclient import TestClient


def test_readiness_503_when_partial_disabled(monkeypatch):
    # Ensure required envs are NOT set and partial readiness flag is off
    monkeypatch.delenv("PREDICT_API_KEY", raising=False)
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    monkeypatch.delenv("GRAFANA_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PARTIAL_READINESS", raising=False)
    from core.main import app
    with TestClient(app) as client:
        r = client.get("/health/ready")
        assert r.status_code == 503
        body = r.json()
        # Accept both shapes: {"detail": {...}} or direct {...}
        payload = body.get("detail") if isinstance(body, dict) and isinstance(body.get("detail"), dict) else None
        if isinstance(payload, dict):
            assert payload.get("status") == "not_ready"
            assert isinstance(payload.get("missing"), list) and payload.get("missing")
        else:
            # Fallback: custom error envelope; assert informative fields are present in string form
            s = str(body)
            assert "not_ready" in s
            assert "PREDICT_API_KEY" in s and "PROMETHEUS_URL" in s and "GRAFANA_BASE_URL" in s
