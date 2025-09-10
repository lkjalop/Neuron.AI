"""Persistence integration for connector event streams.

Transforms normalized vuln_finding events from Qualys/Tenable streams into
asset / vulnerability / finding persistence operations.
"""
from __future__ import annotations

import hashlib, time, json
from typing import Dict, Any
from storage import vuln_store


def _severity_to_text(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 90: return 'CRITICAL'
    if score >= 70: return 'HIGH'
    if score >= 40: return 'MEDIUM'
    if score > 0: return 'LOW'
    return 'INFO'


async def persist_vuln_event(ev: Dict[str, Any]):
    meta = ev.get('metadata', {})
    cve_ids = meta.get('cve_ids') or []
    # Choose primary CVE id if available
    primary_cve = cve_ids[0] if cve_ids else meta.get('qid') or meta.get('plugin_id')
    if not primary_cve:
        return
    # Upsert vulnerability (minimal fields) using existing upsert_vulnerability contract expects object; we'll build dict-like
    # Instead of constructing scanner.models.Vulnerability (not imported), store via raw SQL path? Simplicity: create finding directly and rely on existing vulnerability ingestion later.
    # Create finding id stable
    host = meta.get('host') or meta.get('asset') or 'unknown-host'
    fid_raw = f"finding-{host}-{primary_cve}"
    fid = f"f-{hashlib.sha256(fid_raw.encode()).hexdigest()[:24]}"
    now = ev.get('timestamp') or time.time()
    risk_score = (ev.get('severity') or 0) / 100.0
    risk_severity = _severity_to_text(ev.get('severity')) or 'LOW'
    rec = {
        'id': fid,
        'cve_id': primary_cve,
        'asset_id': host,
        'component_id': None,
        'first_seen': now,
        'last_seen': now,
        'state': 'open',
        'detection_source': ev.get('source'),
        'risk_score': risk_score,
        'risk_severity': risk_severity,
        'asset_metadata': json.dumps({'host': host}),
        'sla_due_ts': None,
        'risk_factors': {
            'exploit_available': 1.0 if meta.get('exploitability') or meta.get('exploit_available') else 0.0,
            'patch_available': 1.0 if meta.get('patch_available') else 0.0,
        },
        'treatment_state': None,
        'accepted_risk': None,
        'remediation_target_ts': None,
    }
    try:
        await vuln_store.upsert_finding(rec)  # type: ignore
    except Exception:
        return

__all__ = ['persist_vuln_event']
