from __future__ import annotations
import os, json, pathlib
from fastapi.testclient import TestClient
from core.main import app
from config import flags as _flags, runtime_params
from config.flags import refresh as refresh_flags
from scripts import rag_ingest

client = TestClient(app)

ADMIN_KEY = "testkey"
os.environ["ADMIN_API_KEY"] = ADMIN_KEY


def _auth_headers():
    return {"x-api-key": ADMIN_KEY}


def test_feedback_disabled_returns_403(monkeypatch):
    # Ensure flag disabled
    os.environ.pop("NEURON_FEEDBACK_INGEST_ENABLED", None)
    refresh_flags()
    resp = client.post("/feedback", json={"query": "q"}, headers=_auth_headers())
    assert resp.status_code == 403


def test_feedback_append_and_chain(tmp_path, monkeypatch):
    os.environ["NEURON_FEEDBACK_INGEST_ENABLED"] = "1"
    refresh_flags()
    # Prepare minimal retrieval artifact for provenance hashes
    d1 = tmp_path / "x.md"
    d1.write_text("alpha beta gamma", encoding="utf-8")
    idx, chunks, manifest = rag_ingest.build_index([d1])
    # Take first manifest hash
    h = manifest[0]["hash"]
    body = {
        "query": "alpha",
        "retrieved_chunk_ids": ["x.md:0"],
        "relevance": 1,
        "notes": "useful",
        "provenance_hashes": [h],
    }
    resp1 = client.post("/feedback", json=body, headers=_auth_headers())
    assert resp1.status_code == 200
    prev_hash = resp1.json()["hash"]
    body["notes"] = "second"
    resp2 = client.post("/feedback", json=body, headers=_auth_headers())
    assert resp2.status_code == 200
    assert resp2.json()["prev"] == prev_hash


def test_insight_context_enrichment(monkeypatch, tmp_path):
    # Enable flags
    os.environ["NEURON_INSIGHT_CONTEXT_ENRICH_ENABLED"] = "1"
    os.environ["NEURON_RETRIEVAL_DOCS_ENABLED"] = "1"
    os.environ["NEURON_RETRIEVAL_EXPLANATIONS_ENABLED"] = "1"
    refresh_flags()
    runtime_params.update_param("insight.context.min_severity", 0.0, reason="test")
    runtime_params.update_param("insight.context.top_k", 2, reason="test")
    # Build retrieval artifacts by emitting index files (simulate script output minimal)
    d1 = tmp_path / "a.md"
    d1.write_text("temporal uplift variance", encoding="utf-8")
    idx, chunks, manifest = rag_ingest.build_index([d1])
    # Persist simplified artifacts for interface consumption
    out_dir = pathlib.Path("artifacts/retrieval")
    out_dir.mkdir(parents=True, exist_ok=True)
    import time
    ts = int(time.time())
    # index: token -> list(doc, chunk_id)
    slim = {tok: [(d, cid) for (d, cid, _t) in postings] for tok, postings in idx.items()}
    (out_dir / f"index_{ts}.json").write_text(json.dumps(slim), encoding="utf-8")
    (out_dir / f"manifest_{ts}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    resp = client.get("/insights", params={"tenant": "tenantA"}, headers=_auth_headers())
    assert resp.status_code == 200
    payload = resp.json()
    # If any insight present with severity >= 0 should have (optional) context field (may be empty if no category matches tokens)
    for ins in payload.get("insights", []):
        if ins.get("severity", 0) >= 0.0:
            assert "context" in ins
