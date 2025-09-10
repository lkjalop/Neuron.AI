from core.normalizer import normalize_raw_event
import os


def test_normalizer_ip_domain_extraction(monkeypatch):
    raw = {
        "timestamp": 1234567890,
        "severity": 5,
        "message": "Connection from 10.1.2.3 to api.example.com using token=abcdefabcdefabcdefabcdefabcdefab",
    }
    evt = normalize_raw_event(raw)
    assert evt.features.get("severity") == 5.0
    assert "ips" in evt.metadata and len(evt.metadata["ips"]) >= 1
    assert "domains" in evt.metadata and "api.example.com" in evt.metadata["domains"]
    assert evt.features.get("redactions") == 1  # secret redacted


def test_normalizer_redaction_toggle(monkeypatch):
    monkeypatch.setenv("ENABLE_REDACTION", "false")
    raw = {
        "timestamp": 1234567890,
        "severity": 1,
        "message": "Plain text 10.2.3.4 token=abcdefabcdefabcdefabcdefabcdefab",
    }
    evt = normalize_raw_event(raw)
    # Should still extract IP but not redact secret (so no redactions feature)
    assert "ips" in evt.metadata
    assert evt.features.get("redactions") is None
