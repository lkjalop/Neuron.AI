from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class Asset:
    id: str
    tenant_id: str
    asset_type: str
    name: str
    env: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    first_seen_ts: Optional[datetime] = None
    last_seen_ts: Optional[datetime] = None

@dataclass
class Component:
    id: str
    name: str
    version: str
    ecosystem: str
    purl: Optional[str] = None
    license: Optional[str] = None
    hash: Optional[str] = None
    created_ts: Optional[datetime] = None
    raw_json: Dict[str, Any] | None = None

@dataclass
class Vulnerability:
    id: str
    cve_id: str
    aliases: List[str]
    cvss_base: Optional[float]
    cvss_vector: Optional[str]
    severity: Optional[str]
    cwe_ids: List[str]
    published_ts: Optional[datetime]
    modified_ts: Optional[datetime]
    exploit_available: bool
    epss: Optional[float]
    kev_listed: bool
    source: Optional[str] = None
    raw_json: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Finding:
    id: str
    tenant_id: str
    vulnerability_id: str
    component_id: str
    asset_id: Optional[str]
    introduced_ts: datetime
    detected_ts: datetime
    status: str
    status_reason: Optional[str]
    last_status_change_ts: datetime
    sla_due_ts: Optional[datetime]
    risk_score: Optional[float]
    last_risk_calc_ts: Optional[datetime]
    meta: Dict[str, Any] = field(default_factory=dict)
    asset_metadata: Dict[str, Any] = field(default_factory=dict)

__all__ = [
    "Asset","Component","Vulnerability","Finding"
]
