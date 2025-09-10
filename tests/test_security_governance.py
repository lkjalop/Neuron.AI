import os, json, tempfile, pathlib, subprocess, sys, time, base64, hmac, hashlib
from fastapi.testclient import TestClient

from core.main import app


def test_admin_api_key_guard_denies_without_key(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    client = TestClient(app)
    r = client.get("/admin/params")
    assert r.status_code == 503


def test_admin_api_key_allows_with_correct_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret123")
    client = TestClient(app)
    r = client.get("/admin/params", headers={"x-api-key": "secret123"})
    assert r.status_code == 200
    assert "params" in r.json()


def _hmac(key: str, method: str, path: str, body: bytes, ts: float) -> str:
    canonical = json.dumps({
        "method": method,
        "path": path,
        "timestamp": str(ts),
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }, sort_keys=True)
    mac = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


def test_hmac_signed_update(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "k123")
    monkeypatch.setenv("ADMIN_HMAC_REQUIRED", "true")
    client = TestClient(app)
    payload = {"key": "baseline.use_hybrid", "value": True, "reason": "test"}
    body = json.dumps(payload).encode()
    ts = time.time()
    sig = _hmac("k123", "POST", "/admin/params/update", body, ts)
    r = client.post("/admin/params/update", data=body, headers={
        "x-api-key": "k123",
        "x-timestamp": str(ts),
        "x-signature": sig,
        "Content-Type": "application/json",
    })
    assert r.status_code == 200, r.text


def test_tenant_scope_denied(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "k123")
    monkeypatch.setenv("ADMIN_TENANT_SCOPE", "tenantX")
    client = TestClient(app)
    ts = time.time()
    body = b""
    sig = _hmac("k123", "GET", "/anomalies", body, ts)
    r = client.get("/anomalies?tenant=tenantA", headers={
        "x-api-key": "k123",
        "x-timestamp": str(ts),
        "x-signature": sig,
    })
    assert r.status_code == 403


def test_verify_integrity_detects_mismatch(tmp_path):
    # Create fake artifact and gate report referencing a wrong hash
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    bad_hash = "0" * 64
    gate = {
        "artifacts": {
            "test_artifact": {"path": str(artifact), "sha256": bad_hash}
        },
        "canonical_doc_hash": "irrelevant"
    }
    gate_path = tmp_path / "gate_report.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    # Run integrity script
    cmd = [sys.executable, "scripts/verify_integrity.py", "--gate", str(gate_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "fail"
    assert any(f.startswith("HASH_MISMATCH:test_artifact") for f in data["failures"]) 
