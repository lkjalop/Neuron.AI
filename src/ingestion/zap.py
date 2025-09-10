"""ZAP JSON report ingestion adapter.

Parses a ZAP JSON export (traditional or API JSON) and converts alerts into
finding upsert records with detection_source='zap_scan'.

Minimal expected ZAP structure (simplified):
{
  "site": [
    {
      "@name": "https://example.com",
      "alerts": [
        {
          "pluginid": "40012",
          "name": "Cross Site Scripting (Reflected)",
          "riskcode": "3",
          "confidence": "2",
          "riskdesc": "High (Medium)",
          "description": "...",
          "solution": "...",
          "reference": "...",
          "cweid": "79",
          "wascid": "8",
          "instances": [ { "uri": "https://example.com/path", "method": "GET" } ]
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

from typing import Dict, Any, Iterable, List
import time
import hashlib
import json

from storage.vuln_store import upsert_finding  # type: ignore

RISK_MAP = {
    "0": (0.05, "INFO"),
    "1": (0.25, "LOW"),
    "2": (0.50, "MEDIUM"),
    "3": (0.75, "HIGH"),
    "4": (0.90, "CRITICAL"),
}

async def ingest_zap_report(report: Dict[str, Any], asset_id: str | None = None) -> int:
    count = 0
    sites = report.get("site") or []
    now = time.time()
    for site in sites:
        alerts = site.get("alerts") or []
        for alert in alerts:
            plugin_id = str(alert.get("pluginid"))
            name = alert.get("name") or f"ZAP-{plugin_id}"
            riskcode = str(alert.get("riskcode"))
            base_score, sev = RISK_MAP.get(riskcode, (0.4, "MEDIUM"))
            cweid = alert.get("cweid")
            # Synthesize a pseudo vulnerability id keyed by plugin + cwe for grouping
            pseudo_vuln_id = f"ZAP-{plugin_id}-{cweid or 'NA'}"
            # Deterministic finding id: hash site + name
            raw = f"zap-{site.get('@name')}-{plugin_id}-{cweid}".encode()
            fid = f"f-{hashlib.sha256(raw).hexdigest()[:24]}"
            factors = {
                "zap_plugin": plugin_id,
                "zap_riskcode": riskcode,
                "source": "zap",
            }
            meta = {
                "description": alert.get("description"),
                "solution": alert.get("solution"),
                "reference": alert.get("reference"),
                "instances": alert.get("instances"),
                "site": site.get("@name"),
            }
            rec = {
                "id": fid,
                "cve_id": pseudo_vuln_id,  # stored in findings.cve_id column for reuse of existing schema
                "asset_id": asset_id or site.get("@name") or "web-target",
                "component_id": None,
                "first_seen": now,
                "last_seen": now,
                "state": "open",
                "detection_source": "zap_scan",
                "risk_score": base_score,
                "risk_severity": sev,
                "asset_metadata": json.dumps(meta),
                "sla_due_ts": None,
                "risk_factors": factors,
                "treatment_state": None,
                "accepted_risk": None,
                "remediation_target_ts": None,
            }
            try:
                await upsert_finding(rec)
                count += 1
            except Exception:
                continue
    return count

__all__ = ["ingest_zap_report"]
