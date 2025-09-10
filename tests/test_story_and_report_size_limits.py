from fastapi.testclient import TestClient
from core.main import app, _create_case  # type: ignore
import os

def test_story_size_limit(monkeypatch):
    client = TestClient(app)
    c = _create_case('story-size-case', tenant='tstory')
    # Set very small size limit via env for story
    monkeypatch.setenv('STORY_MAX_CONTENT_BYTES', '50')
    big_content = 'A' * 120
    r = client.post('/story', json={'case_id': c['id'], 'content': big_content}, headers={'x-api-key':'adminkey'})
    assert r.status_code == 413, r.text


def test_report_commit_size_limit(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv('REPORT_MAX_CONTENT_BYTES', '40')
    big = 'B' * 200
    r = client.post('/report/commit', json={'content': big}, headers={'x-api-key':'adminkey'})
    assert r.status_code == 413, r.text


def test_report_diff_apply_size_limit(monkeypatch):
    client = TestClient(app)
    # Allow commit with larger limit, then tighten for diff apply
    monkeypatch.setenv('REPORT_MAX_CONTENT_BYTES', '200')
    base = client.post('/report/commit', json={'content': 'Line1'}, headers={'x-api-key':'adminkey'})
    assert base.status_code == 200
    vid = base.json()['version']['version_id']
    monkeypatch.setenv('REPORT_MAX_CONTENT_BYTES', '10')
    rdiff = client.post('/report/diff/apply', json={'base_version_id': vid, 'new_content': 'Line1\nExtraLongLineThatExceeds'}, headers={'x-api-key':'adminkey'})
    assert rdiff.status_code == 413, rdiff.text
