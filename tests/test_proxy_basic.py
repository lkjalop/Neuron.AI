import os, json
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('src').resolve()))
from fastapi.testclient import TestClient
from core.main import app  # type: ignore

client = TestClient(app)

PREDICT_HEADER = {"x-api-key": os.getenv("PREDICT_API_KEY", "predictkey")}


def test_promql_invalid_expr_returns_400(monkeypatch):
    # Ensure prometheus configured to pass config guard (we won't reach upstream)
    monkeypatch.setenv('PROMETHEUS_URL', 'http://prometheus:9090')
    r = client.get('/proxy/prom', params={'q': 'up\ninvalid'}, headers=PREDICT_HEADER)
    assert r.status_code == 400
    assert 'invalid_expr' in r.text


def test_grafana_unconfigured_returns_503(monkeypatch):
    # Unset to force 503
    monkeypatch.delenv('GRAFANA_BASE_URL', raising=False)
    r = client.get('/proxy/grafana/iframe?panelId=1', headers=PREDICT_HEADER)
    assert r.status_code == 503
    assert 'grafana_unconfigured' in r.text


def test_grafana_iframe_with_time_vars(monkeypatch):
    monkeypatch.setenv('GRAFANA_BASE_URL', 'http://grafana:3000')
    r = client.get('/proxy/grafana/iframe?panelId=1&fr=now-6h&to=now&vars=%7B%22tenant%22%3A%22t%22%7D', headers=PREDICT_HEADER)
    assert r.status_code == 200
    js = r.json(); assert 'url' in js and 'from=now-6h' in js['url'] and 'to=now' in js['url']
