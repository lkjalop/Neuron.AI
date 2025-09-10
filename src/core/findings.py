from __future__ import annotations
import sqlite3, os, time, json, uuid
from typing import Dict, Any, Optional, List

_SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "artifacts/neuron.db")

DDL = """
CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  project_id TEXT,
  type TEXT,
  title TEXT,
  description TEXT,
  severity TEXT,
  confidence REAL,
  citation_count INTEGER,
  citation_coverage REAL,
  unsupported_entities INTEGER,
  created_at REAL,
  updated_at REAL,
  status TEXT DEFAULT 'draft',
  source_context TEXT
);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(tenant_id, status, severity);
"""

def _cx():
    cx = sqlite3.connect(_SQLITE_PATH)
    cx.executescript(DDL)
    return cx

def create_finding(tenant_id: str | None, project_id: str | None, data: Dict[str, Any]) -> Dict[str, Any]:
    fid = data.get("finding_id") or str(uuid.uuid4())
    now = time.time()
    row = {
        "finding_id": fid,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "type": data.get("type", "vuln"),
        "title": data.get("title", "Untitled Finding"),
        "description": data.get("description", ""),
        "severity": data.get("severity", "INFO"),
        "confidence": float(data.get("confidence", 0.0)),
        "citation_count": int(data.get("citation_count", 0)),
        "citation_coverage": float(data.get("citation_coverage", 0.0)),
        "unsupported_entities": int(data.get("unsupported_entities", 0)),
        "created_at": now,
        "updated_at": now,
        "status": data.get("status", "draft"),
        "source_context": json.dumps(data.get("source_context", {}))[:16000],
    }
    cx = _cx()
    placeholders = ",".join([":"+k for k in row.keys()])
    cols = ",".join(row.keys())
    cx.execute(f"INSERT OR REPLACE INTO findings ({cols}) VALUES ({placeholders})", row)
    cx.commit(); cx.close()
    return row

def get_finding(finding_id: str) -> Optional[Dict[str, Any]]:
    cx = _cx(); cur = cx.cursor()
    cur.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,))
    colnames = [d[0] for d in cur.description]
    row = cur.fetchone()
    cx.close()
    if not row:
        return None
    rec = dict(zip(colnames, row))
    try:
        if rec.get("source_context"):
            rec["source_context"] = json.loads(rec["source_context"])
    except Exception:
        pass
    return rec

def list_findings(tenant_id: str | None, project_id: str | None, limit: int = 100) -> List[Dict[str, Any]]:
    cx = _cx(); cur = cx.cursor()
    if tenant_id:
        cur.execute("SELECT * FROM findings WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?", (tenant_id, limit))
    else:
        cur.execute("SELECT * FROM findings ORDER BY created_at DESC LIMIT ?", (limit,))
    colnames = [d[0] for d in cur.description]
    rows = [dict(zip(colnames, r)) for r in cur.fetchall()]
    cx.close()
    for r in rows:
        try:
            if r.get("source_context"):
                r["source_context"] = json.loads(r["source_context"])
        except Exception:
            pass
    return rows

__all__ = ["create_finding", "get_finding", "list_findings"]
