"""SOAR action dispatch skeleton."""
from __future__ import annotations

from typing import Dict, Any
import time

_ACTION_LOG: list[Dict[str, Any]] = []


def open_ticket(finding_id: str, summary: str) -> str:
    tid = f"TCK-{int(time.time())}-{len(_ACTION_LOG)}"
    _ACTION_LOG.append({'type': 'ticket', 'id': tid, 'finding_id': finding_id, 'summary': summary})
    return tid


def trigger_scan(asset_id: str, scan_type: str = 'qualys') -> str:
    sid = f"SCAN-{int(time.time())}-{asset_id}"
    _ACTION_LOG.append({'type': 'scan', 'id': sid, 'asset_id': asset_id, 'scan_type': scan_type})
    return sid


def accept_risk(finding_id: str, reason: str) -> str:
    rid = f"RISK-{int(time.time())}-{finding_id}"
    _ACTION_LOG.append({'type': 'risk_accept', 'id': rid, 'finding_id': finding_id, 'reason': reason})
    return rid


def list_actions() -> list[Dict[str, Any]]:
    return list(_ACTION_LOG)

__all__ = ['open_ticket', 'trigger_scan', 'accept_risk', 'list_actions']
