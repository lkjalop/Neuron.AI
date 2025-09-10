from fastapi.testclient import TestClient
from core.main import app, _create_case, _story_sig  # type: ignore

def test_story_create_and_fetch(monkeypatch):
    client = TestClient(app)
    c = _create_case('story-case-1', tenant='tstory')
    r = client.post('/story', json={'case_id': c['id'], 'title': 'My Story', 'content': 'Story body'}, headers={"x-api-key":"adminkey"})
    assert r.status_code == 200, r.text
    share_id = r.json()['story']['share_id']
    # fetch
    # Use public signature fetch
    pub = r.json()['public_share']
    r2 = client.get(f"/story/{share_id}?sig={pub['sig']}&exp={pub['exp']}")
    assert r2.status_code == 200
    js2 = r2.json()
    assert js2['story']['case_id'] == c['id']
    # ensure ttl field present
    assert 'ttl_remaining' in js2


def test_story_auto_content(monkeypatch):
    client = TestClient(app)
    c = _create_case('story-case-2', tenant='tstory')
    r = client.post('/story', json={'case_id': c['id']}, headers={"x-api-key":"adminkey"})
    assert r.status_code == 200
    story = r.json()['story']
    assert story['content']


def test_story_not_found(monkeypatch):
    client = TestClient(app)
    r = client.get('/story/doesnotexist?sig=bad&exp=0')
    assert r.status_code == 404

def test_story_requires_auth_without_sig():
    client = TestClient(app)
    c = _create_case('story-case-auth', tenant='tstory')
    r = client.post('/story', json={'case_id': c['id'], 'content': 'x'}, headers={"x-api-key":"adminkey"})
    share_id = r.json()['story']['share_id']
    # No sig and no api key -> 401
    r2 = client.get(f"/story/{share_id}")
    assert r2.status_code == 401
    # With api key works
    r3 = client.get(f"/story/{share_id}", headers={"x-api-key":"adminkey"})
    assert r3.status_code == 200
    # Original story creation must succeed (already asserted via JSON access). No extra 404 assertion.
