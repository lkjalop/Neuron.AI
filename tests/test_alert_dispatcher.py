import os, json
from core.alerts.dispatcher import AlertDispatcher
from config import runtime_params


def test_dead_letter_on_webhook_failure(monkeypatch, tmp_path):
    # Enable alerts and webhook with bogus URL to force failure
    runtime_params.update_param("alerts.enabled", True, reason="test", actor="test")
    runtime_params.update_param("alerts.webhook.enabled", True, reason="test", actor="test")
    runtime_params.update_param("alerts.webhook.url", "http://127.0.0.1:9/does-not-exist", reason="test", actor="test")
    disp = AlertDispatcher()
    # Point dead-letter to tmp
    monkeypatch.setattr(disp, "_dead_letter_path", tmp_path / "dead.jsonl")
    res = disp.dispatch({"msg":"x"})
    # Expect an error result for webhook
    assert any(r.get("channel") == "webhook" and r.get("status", "").startswith("error:") for r in res.get("results", []))
    # Dead-letter file created
    dl = tmp_path / "dead.jsonl"
    assert dl.exists(), "dead-letter file not created"
    data = dl.read_text(encoding='utf-8').strip().splitlines()
    assert data and json.loads(data[-1]).get("channel") == "webhook"


def test_dead_letter_persistence_across_instances(monkeypatch, tmp_path):
    from core.alerts.dispatcher import AlertDispatcher
    from config import runtime_params
    # Configure failing webhook
    runtime_params.update_param("alerts.enabled", True, reason="test", actor="test")
    runtime_params.update_param("alerts.webhook.enabled", True, reason="test", actor="test")
    runtime_params.update_param("alerts.webhook.url", "http://127.0.0.1:9/does-not-exist", reason="test", actor="test")
    # First instance writes dead-letter
    d1 = AlertDispatcher()
    monkeypatch.setattr(d1, "_dead_letter_path", tmp_path / "dead.jsonl")
    _ = d1.dispatch({"msg": "x"})
    dl = tmp_path / "dead.jsonl"
    assert dl.exists()
    size1 = dl.stat().st_size
    # New instance should append to same file when pointed to same path
    d2 = AlertDispatcher()
    monkeypatch.setattr(d2, "_dead_letter_path", tmp_path / "dead.jsonl")
    _ = d2.dispatch({"msg": "y"})
    size2 = dl.stat().st_size
    assert size2 > size1, "dead-letter file not appended by new instance"