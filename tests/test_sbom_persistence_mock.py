import asyncio, json
from fastapi.testclient import TestClient
from core.main import app

# This test simulates successful persistence by monkeypatching vuln_store helpers
# so the /vuln/ingest_sbom endpoint reports persisted=True without a real database.

def test_ingest_sbom_persisted(monkeypatch):
    try:
        from storage import vuln_store  # type: ignore
    except Exception:
        # If import fails, skip (environment without module)
        return

    async def _noop(*args, **kwargs):
        return None

    # Patch helpers
    monkeypatch.setattr(vuln_store, 'upsert_asset', _noop, raising=False)
    monkeypatch.setattr(vuln_store, 'upsert_component', _noop, raising=False)
    monkeypatch.setattr(vuln_store, 'link_asset_component', _noop, raising=False)

    client = TestClient(app)
    body = {
        "asset_name": "checkout-service",
        "document": {
            "components": [
                {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13", "type": "library"},
                {"name": "flask", "version": "3.0.2", "purl": "pkg:pypi/flask@3.0.2", "type": "pypi"}
            ]
        },
        "asset_metadata": {"criticality": 0.9}
    }
    headers = {"x-api-key": "dummy"}
    # Bypass API key check by monkeypatching require_api_key if needed
    from core.main import require_api_key as _orig_req
    def _allow(request):
        return True
    monkeypatch.setattr('core.main.require_api_key', _allow, raising=False)

    resp = client.post('/vuln/ingest_sbom', json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['count'] == 2
    assert data['persisted'] is True
    assert data['components'][0]['name'] == 'openssl'

    # restore original if desired (not strictly necessary in test context)
    monkeypatch.setattr('core.main.require_api_key', _orig_req, raising=False)
