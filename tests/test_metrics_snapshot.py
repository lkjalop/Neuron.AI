import re, pathlib
from fastapi.testclient import TestClient
from src.core.main import app
from prometheus_client import generate_latest

SNAPSHOT_PATH = pathlib.Path(__file__).parent / 'metrics_snapshot.txt'

client = TestClient(app)

def test_metrics_snapshot_presence():
    # Load snapshot list
    expected = {line.strip() for line in SNAPSHOT_PATH.read_text().splitlines() if line.strip() and not line.startswith('#')}
    # Scrape current metrics
    resp = client.get('/metrics')
    assert resp.status_code == 200
    text = resp.text
    present = set(re.findall(r'^# HELP (neuron_[a-zA-Z0-9_]+) ', text, flags=re.M))
    missing = sorted(expected - present)
    # Allow newly added metrics (not in snapshot) but fail if snapshot metrics disappeared
    assert not missing, f"Missing metrics compared to snapshot: {missing[:20]}{'...' if len(missing)>20 else ''}"
