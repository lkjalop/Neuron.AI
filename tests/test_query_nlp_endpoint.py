import pytest
from fastapi.testclient import TestClient
from core.main import app

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PREDICT_API_KEY', 'testkey')
    return TestClient(app)


def test_nlp_endpoint_low_confidence(client):
    r = client.post('/query/nlp', json={'query':'zzzzword yyyjunk'}, headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['ir']['meta']['confidence'] < 0.4
    # preview should be empty
    assert data['preview']['count'] == 0


def test_nlp_endpoint_confident_preview(client, monkeypatch):
    # Monkeypatch vuln_store.list_vulnerabilities to return synthetic rows for preview
    async def fake_list_vulns(severity=None, exploit_only=False, limit=20):
        rows = [
            {'cve_id':'CVE-2024-1111','published_ts':0,'severity':severity or 'CRITICAL','exploit_available':True},
            {'cve_id':'CVE-2024-2222','published_ts':0,'severity':severity or 'CRITICAL','exploit_available':True},
        ][:limit]
        return rows
    import core.main as cm
    # Only patch if underlying vuln_store exists; else create dummy module attr
    if cm.vuln_store is None:
        class Dummy:
            pass
        cm.vuln_store = Dummy()
    monkeypatch.setattr(cm.vuln_store, 'list_vulnerabilities', fake_list_vulns)

    r = client.post('/query/nlp?preview_limit=2', json={'query':'critical exploit top 2'}, headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    assert data['ir']['meta']['confidence'] >= 0.4
    assert data['preview']['count'] <= 2
    # Should include at least one item
    assert data['preview']['count'] >= 1
