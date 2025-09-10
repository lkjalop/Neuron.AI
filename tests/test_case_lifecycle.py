import sys, json, time
import pathlib
sys.path.insert(0, str(pathlib.Path('src').resolve()))
from fastapi.testclient import TestClient
from core.main import app  # type: ignore
from core import metrics

client = TestClient(app)
API_KEY_HEADER = {"x-api-key": "adminkey"}

def _create_case():
    # Use anomaly -> case creation path
    anomaly_id = 'anom-' + str(time.time())
    r = client.post(f"/cases/from_anomaly/{anomaly_id}", headers=API_KEY_HEADER)
    assert r.status_code == 200
    cid = r.json()["case"]["id"]
    return cid

def test_case_close_reopen_cycle():
    cid = _create_case()
    # Close
    r = client.post(f"/cases/{cid}/close", json={"reason": "test"}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "closed"
    # Reopen
    r = client.post(f"/cases/{cid}/reopen", json={"in_progress": True}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    js = r.json()
    assert js["status"] in {"in_progress", "reopened"}
    # Explicit set status
    r = client.post(f"/cases/{cid}/status", json={"status": "open"}, headers=API_KEY_HEADER)
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "open"

    # Metrics presence sanity (do not assert exact numeric values to avoid flakiness)
    reg_text = client.get('/metrics', headers=API_KEY_HEADER).text
    for fam in [
        'neuron_case_closures_total',
        'neuron_case_reopens_total',
        'neuron_case_status_total',
        'neuron_case_total'
    ]:
        assert fam in reg_text
