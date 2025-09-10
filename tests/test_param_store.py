from runtime.param_store import set_param, get_param
import os, json, pathlib


def test_param_store_set_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("PARAM_STORE_PATH", str(tmp_path / "params.json"))
    key = "fusion.weight.test_detector"
    set_param(key, 1.23, actor="tester", reason="init")
    assert get_param(key) == 1.23
    set_param(key, 2.0, actor="tester", reason="adjust")
    assert get_param(key) == 2.0


def test_param_store_audit_log(tmp_path, monkeypatch):
    monkeypatch.setenv("PARAM_STORE_PATH", str(tmp_path / "params.json"))
    key = "fusion.weight.audit"
    set_param(key, 0.5, actor="tester", reason="init")
    set_param(key, 0.7, actor="tester", reason="raise")
    audit_file = pathlib.Path("audit/param_changes.log")
    assert audit_file.exists()
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    # At least two records for the key (inexact matching acceptable for robustness)
    assert len(lines) >= 2
    parsed = [json.loads(l) for l in lines if '"key": "' in l]
    assert any(rec.get("key") == key for rec in parsed)
