import time
import pytest
from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

# Helpers to post domain events

def _post_edr(ev: dict):
    return client.post("/ingest/edr", json=ev)

def _post_dns(ev: dict):
    return client.post("/ingest/dns", json=ev)

def _post_netflow(ev: dict):
    return client.post("/ingest/netflow", json=ev)

@pytest.mark.timeout(10)
def test_lateral_movement_detector_triggers():
    # Same user hitting many distinct destination IPs
    user = "alice"
    for i in range(7):
        ev = {"user": user, "dst_ip": f"10.0.0.{i+1}", "process_name": "ssh.exe"}
        r = _post_edr(ev)
        assert r.status_code == 200
    # Fetch recent anomalies (assuming shared buffer endpoint exists or rely on inline response soon reaction)
    # For now we rely that at least one ingest produced anomaly in the last response anomalies list
    last = r.json()
    assert isinstance(last, dict)
    anoms = last.get("anomalies") or []
    # If pipeline doesn't return anomalies inline, this test may need adaptation; assert graceful structure
    found = any(a.get("detector") == "lateral_movement" for a in anoms)
    assert found, f"Expected lateral_movement anomaly, got: {anoms}"

@pytest.mark.timeout(10)
def test_persistence_detector_triggers():
    # suspicious parent-child combo
    ev = {"user": "bob", "process_name": "reg.exe", "parent_process": "powershell.exe", "command_line": "reg add HKCU\\Software\\Run"}
    r = _post_edr(ev)
    assert r.status_code == 200
    anoms = r.json().get("anomalies") or []
    assert any(a.get("detector") == "persistence" for a in anoms)

@pytest.mark.timeout(15)
def test_beaconing_detector_triggers():
    src = "192.168.1.10"
    dst = "8.8.8.8"
    # Rapid periodic netflow events to build low-jitter intervals
    for _ in range(6):
        r = _post_netflow({"src_ip": src, "dst_ip": dst, "bytes": 150})
        assert r.status_code == 200
        time.sleep(0.2)
    anoms = r.json().get("anomalies") or []
    assert any(a.get("detector") == "beaconing" for a in anoms)

@pytest.mark.timeout(10)
def test_dns_tunneling_detector_triggers():
    # Long high-entropy subdomain label
    sub = "x" + "ab" + "".join([chr(97 + (i % 26)) for i in range(40)])
    query = f"{sub}.example.com"
    r = _post_dns({"query": query})
    assert r.status_code == 200
    anoms = r.json().get("anomalies") or []
    assert any(a.get("detector") == "dns_tunneling" for a in anoms)

@pytest.mark.timeout(10)
def test_enrichments_present():
    # Reuse persistence anomaly generation to check enrichment fields
    ev = {"user": "carol", "process_name": "reg.exe", "parent_process": "powershell.exe"}
    r = _post_edr(ev)
    anoms = r.json().get("anomalies") or []
    target = next((a for a in anoms if a.get("detector") == "persistence"), None)
    assert target is not None, "Expected persistence anomaly"
    assert "mitre_techniques" in target and target["mitre_techniques"], "MITRE enrichment missing"
    assert "threat_intel" in target and target["threat_intel"].get("score") is not None, "Threat intel enrichment missing"


@pytest.mark.timeout(10)
def test_negative_lateral_movement_not_triggered():
    # Single user reusing SAME destination should not trip distinct dest threshold
    user = "neguser"
    dst = "10.10.10.5"
    triggered = False
    for _ in range(6):
        r = _post_edr({"user": user, "dst_ip": dst})
        assert r.status_code == 200
        anoms = r.json().get("anomalies") or []
        if any(a.get("detector") == "lateral_movement" for a in anoms):
            triggered = True
            break
    assert not triggered, "Lateral movement should not trigger on repeated same destination"

@pytest.mark.timeout(10)
def test_negative_beaconing_not_triggered_high_jitter():
    src = "172.16.0.9"
    dst = "9.9.9.9"
    # Introduce irregular sleeps to create high jitter
    import random
    triggered = False
    for _ in range(7):
        r = _post_netflow({"src_ip": src, "dst_ip": dst, "bytes": 42})
        assert r.status_code == 200
        anoms = r.json().get("anomalies") or []
        if any(a.get("detector") == "beaconing" for a in anoms):
            triggered = True
            break
        time.sleep(random.uniform(0.05, 0.6))
    assert not triggered, "Beaconing should not trigger under high jitter intervals"

@pytest.mark.timeout(10)
def test_negative_dns_tunneling_not_triggered_short_label():
    query = "abc.example.com"  # short, low-entropy
    r = _post_dns({"query": query})
    assert r.status_code == 200
    anoms = r.json().get("anomalies") or []
    assert all(a.get("detector") != "dns_tunneling" for a in anoms), "Short benign DNS label incorrectly flagged"
