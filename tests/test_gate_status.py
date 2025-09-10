import pytest, os, json, time
from fastapi.testclient import TestClient
from core.main import app

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('PREDICT_API_KEY', 'testkey')
    # Ensure artifacts directory exists and create a fake gate report
    artifacts_dir = tmp_path / 'artifacts' / 'gate_report'
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fake_report = artifacts_dir / 'latest.json'
    fake_report.write_text(json.dumps({'ok': True}))
    # Monkeypatch root path used by endpoint by adjusting app _ROOT? _ROOT defined in core.main module
    import core.main as cm
    cm._ROOT = str(tmp_path)
    return TestClient(app)

@pytest.mark.asyncio
async def test_gate_status_artifacts(client):
    r = client.get('/system/gate_status', headers={'x-api-key':'testkey'})
    assert r.status_code == 200
    data = r.json()
    artifacts = data['artifacts']
    assert artifacts['gate_report']['status'] in {'ok','error'}
    assert 'param_chain' in artifacts
    assert 'counts' in data and set(data['counts'].keys()) == {'assets','vulnerabilities','findings'}
