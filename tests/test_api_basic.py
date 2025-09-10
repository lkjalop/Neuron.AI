from __future__ import annotations

import os, pytest, asyncio
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.getenv("NEON_DATABASE_URL"), reason="DB required for API tests")

from api.app import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()
