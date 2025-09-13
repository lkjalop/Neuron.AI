import os
import time
import importlib
from fastapi.testclient import TestClient


def test_metrics_requires_key_when_configured(monkeypatch):
    # Configure predict key and ensure missing header -> 401
    monkeypatch.setenv("PREDICT_API_KEY", "k1")
    # Ensure admin key is not interfering
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    import core.main as m
    importlib.reload(m)
    with TestClient(m.app) as client:
        r = client.get("/metrics")
        assert r.status_code == 401, f"expected 401 without key, got {r.status_code}"
        r2 = client.get("/metrics", headers={"x-api-key": "k1"})
        assert r2.status_code == 200


def test_metrics_throttling_with_key(monkeypatch):
    # Configure key and very tight rate/burst; verify second immediate call is rate limited
    monkeypatch.setenv("PREDICT_API_KEY", "rlkey")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("PREDICT_RATELIMIT_RPS", "0.1")
    monkeypatch.setenv("PREDICT_RATELIMIT_BURST", "1")
    import core.main as m
    importlib.reload(m)
    with TestClient(m.app) as client:
        hdr = {"x-api-key": "rlkey"}
        r1 = client.get("/metrics", headers=hdr)
        assert r1.status_code == 200
        r2 = client.get("/metrics", headers=hdr)
        assert r2.status_code == 429, f"expected 429 on second scrape under tight limits, got {r2.status_code}"
        time.sleep(0.2)
        r3 = client.get("/metrics", headers=hdr)
        assert r3.status_code in (200, 429)
