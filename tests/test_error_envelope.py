import json
from fastapi.testclient import TestClient
from core.main import app
from fastapi import HTTPException
from core.errors import error_payload

client = TestClient(app)

def test_error_payload_shape():
    payload = error_payload("RATE_LIMIT_HOURLY_CAP", "Hourly cap reached", retry_after_s=3600)
    assert 'error' in payload
    assert payload['error']['code'] == 'RATE_LIMIT_HOURLY_CAP'
    assert payload['error']['retry_after_s'] == 3600


def test_guided_session_flow_stub():
    r = client.post('/guided/session', json={'goal': 'test'})
    assert r.status_code == 200
    data = r.json()
    sid = data['session_id']
    # Step forward
    r2 = client.post(f'/guided/session/{sid}/step', json={'direction': 'forward'})
    assert r2.status_code == 200
    # ELI5 queue
    r3 = client.post(f'/guided/session/{sid}/eli5')
    assert r3.status_code == 200
    # Stream placeholder
    r4 = client.get(f'/guided/session/{sid}/stream')
    assert r4.status_code == 200
    assert 'events' in r4.json()


def test_permalink_stub():
    r = client.post('/permalink', json={'resource_type': 'report', 'resource_id': 'r1', 'expires_in_s': 120})
    assert r.status_code == 200
    code = r.json()['code']
    r2 = client.get(f'/p/{code}')
    assert r2.status_code == 200
