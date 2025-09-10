import os, time, json, pathlib, hashlib
import pytest
from fastapi.testclient import TestClient

# Import app
from core.main import app
from config import runtime_params as rp

client = TestClient(app)

ADMIN_KEY = os.getenv("ADMIN_API_KEY", "adminkey-test")
PREDICT_KEY = os.getenv("PREDICT_API_KEY", ADMIN_KEY)

def _auth_headers(admin=True):
    return {"x-api-key": ADMIN_KEY if admin else PREDICT_KEY}

def test_story_ttl_expiry(monkeypatch):
    # Force small TTL via runtime param update
    try:
        rp.update_param("story.ttl_seconds", 1, reason="test_ttl", actor="test")
    except Exception:
        pass
    # Create a case first (POST /cases)
    case_resp = client.post('/cases', json={})
    assert case_resp.status_code == 200
    case_id = case_resp.json()['case']['id']
    # Create story
    story_resp = client.post('/story', headers=_auth_headers(), json={"case_id": case_id, "content": "short content"})
    assert story_resp.status_code == 200
    story = story_resp.json()['story']
    share_id = story['share_id']
    # Advance time beyond TTL by monkeypatching time.time used in fetch handler
    start = time.time()
    monkeypatch.setattr(time, 'time', lambda: start + 5)  # 5s later
    fetch_resp = client.get(f'/story/{share_id}', headers=_auth_headers())
    assert fetch_resp.status_code == 404, fetch_resp.text


def test_story_max_content_override(monkeypatch):
    # Set max content size to schema minimum (100) then send 120 bytes
    try:
        rp.update_param("story.max_content_bytes", 100, reason="test_max", actor="test")
    except Exception:
        pass
    case_resp = client.post('/cases', json={})
    assert case_resp.status_code == 200
    cid = case_resp.json()['case']['id']
    big_content = 'A' * 120  # 120 bytes > 100
    resp = client.post('/story', headers=_auth_headers(), json={"case_id": cid, "content": big_content})
    assert resp.status_code == 413, resp.text


def test_report_integrity_mismatch(monkeypatch, tmp_path):
    # Create a report version
    content = "Line1\nLine2\n"
    commit = client.post('/report/commit', headers=_auth_headers(), json={"content": content})
    assert commit.status_code == 200
    vid = commit.json()['version']['version_id']
    # Tamper in-memory record so scan (which uses in-memory list) detects mismatch
    from core.main import _REPORT_INDEX  # type: ignore
    rec = _REPORT_INDEX.get(vid)
    assert rec is not None
    rec['content'] = rec['content'] + 'X'  # alter content but keep hash
    scan = client.get('/report/integrity/scan', headers=_auth_headers())
    assert scan.status_code == 200
    data = scan.json()
    assert data['mismatches'] >= 1, data
    assert vid in data['mismatch_ids']
