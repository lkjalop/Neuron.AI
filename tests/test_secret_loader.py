import os
import logging
from config.secret_loader import get_secret


def test_secret_loader_optional_and_required(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="secrets")
    # Optional with default
    val = get_secret("NON_EXISTENT_SECRET_X", default="fallback")
    assert val == "fallback"

    # Required missing -> raises
    try:
        get_secret("REQUIRED_MISSING_SECRET", required=True)
        raised = False
    except RuntimeError as e:  # noqa: F841
        raised = True
    assert raised, "Expected RuntimeError for missing required secret"

    # Provided secret present
    monkeypatch.setenv("PRESENT_SECRET", "superSecretValue12345")
    os.environ["LOG_LEVEL"] = "DEBUG"
    val2 = get_secret("PRESENT_SECRET", required=True)
    assert val2 == "superSecretValue12345"

    # Fingerprint present but not raw secret in logs
    logs = "\n".join(m for _, _, m in caplog.record_tuples if "secret loaded" in m)
    assert "superSecretValue12345" not in logs
    assert "len=" in logs or "…" in logs
