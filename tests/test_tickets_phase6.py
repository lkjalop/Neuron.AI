import time, json
from fastapi.testclient import TestClient
from core.main import app
from core import metrics

client = TestClient(app)


def _scrape_metric(name: str):
    # brute force scan default registry
    from prometheus_client import REGISTRY
    for m in REGISTRY.collect():
        if m.name == name:
            return m
    return None


def test_ticket_create_and_get():
    resp = client.post("/tickets/", json={"severity": "high", "priority": 2})
    assert resp.status_code == 200
    data = resp.json()
    tid = data["id"]
    assert data["severity"] == "high"

    get_r = client.get(f"/tickets/{tid}")
    assert get_r.status_code == 200
    assert get_r.json()["id"] == tid


def test_ticket_transition_and_metrics():
    r = client.post("/tickets/", json={"severity": "low", "priority": 4})
    tid = r.json()["id"]
    # transition open -> ack -> in_progress -> closed
    for st in ["ack", "in_progress", "closed"]:
        pr = client.patch(f"/tickets/{tid}", json={"status": st})
        assert pr.status_code == 200
        assert pr.json()["status"] == st
    # metrics presence
    trans = _scrape_metric("neuron_ticket_transitions_total")
    assert trans is not None
    # ensure at least one transition sample collected
    found = False
    for s in trans.samples:
        if s.name == "neuron_ticket_transitions_total" and s.labels.get("to_status") == "closed":
            found = True
            break
    assert found, "expected transition to closed in metrics"


def test_ticket_illegal_transition():
    r = client.post("/tickets/", json={"severity": "medium", "priority": 3})
    tid = r.json()["id"]
    # illegal: open -> closed is allowed per table? we allowed it. Choose closed->ack (illegal)
    client.patch(f"/tickets/{tid}", json={"status": "closed"})
    bad = client.patch(f"/tickets/{tid}", json={"status": "ack"})
    assert bad.status_code == 200
    assert bad.json()["error"] == "invalid_transition"


def test_ticket_sla_breach_counter(monkeypatch):
    r = client.post("/tickets/", json={"severity": "critical", "priority": 1})
    tid = r.json()["id"]
    # Force SLA due in past by editing in-memory object
    from core.tickets import store as ts
    t = ts.get_ticket(tid)
    assert t is not None
    t.sla_due_ts = time.time() - 10
    ts.scan_sla()
    breach = _scrape_metric("neuron_ticket_sla_breach_total")
    assert breach is not None
    assert any(s.labels.get("severity") == "critical" for s in breach.samples if s.name == "neuron_ticket_sla_breach_total")
