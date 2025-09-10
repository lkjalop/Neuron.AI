from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

def test_hourly_cap_error_envelope():
    # Hit limit (3) plus one extra to trigger
    for i in range(3):
        r = client.post('/simulate/hourly-cap')
        assert r.status_code == 200
    r = client.post('/simulate/hourly-cap')
    assert r.status_code == 429
    data = r.json()
    assert data['error']['code'] == 'RATE_LIMIT_HOURLY_CAP'
    assert 'retry_after_s' in data['error']


def test_cooldown_error_envelope():
    # First triggers cooldown
    r1 = client.post('/simulate/cooldown')
    assert r1.status_code == 200
    # Immediate second call should error
    r2 = client.post('/simulate/cooldown')
    assert r2.status_code == 429
    data = r2.json()
    assert data['error']['code'] == 'COOLDOWN_ACTIVE'
    assert data['error']['retry_after_s'] >= 1
