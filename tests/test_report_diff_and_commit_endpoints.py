from fastapi.testclient import TestClient
from core.main import app

def test_report_commit_and_versions():
    client = TestClient(app)
    # initial commit
    r1 = client.post('/report/commit', json={'content': 'Line1\nLine2'}, headers={"x-api-key":"adminkey"})
    assert r1.status_code == 200, r1.text
    v1 = r1.json()['version']['version_id']
    # diff apply against base
    rdiff = client.post('/report/diff/apply', json={'base_version_id': v1, 'new_content': 'Line1\nLine2\nLine3'}, headers={"x-api-key":"adminkey"})
    assert rdiff.status_code == 200
    dj = rdiff.json()
    assert dj['diff']['added_lines'] >= 1
    # commit new version
    r2 = client.post('/report/commit', json={'content': 'Line1\nLine2\nLine3', 'parent_id': v1}, headers={"x-api-key":"adminkey"})
    assert r2.status_code == 200
    v2 = r2.json()['version']['version_id']
    # list versions
    rlist = client.get('/report/versions?limit=5', headers={"x-api-key":"adminkey"})
    assert rlist.status_code == 200
    assert rlist.json()['count'] >= 2
    # fetch single version
    rget = client.get(f'/report/version/{v2}', headers={"x-api-key":"adminkey"})
    assert rget.status_code == 200
    assert 'content' in rget.json()['version']


def test_report_diff_invalid_base():
    client = TestClient(app)
    r = client.post('/report/diff/apply', json={'base_version_id': 'doesnotexist', 'new_content': 'x'}, headers={"x-api-key":"adminkey"})
    assert r.status_code == 404
