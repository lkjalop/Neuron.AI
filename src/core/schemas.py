from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union

class DashboardSnapshot(BaseModel):
    generated_ts: float
    vulnerability_severity: Dict[str, int] = Field(default_factory=dict)
    vulnerability_exploit_available: Dict[str, int] = Field(default_factory=dict)
    open_findings_severity: Dict[str, int] = Field(default_factory=dict)
    new_findings_7d: int
    closed_findings_7d: int
    cached: bool
    stale: bool

class IngestConnectorStatus(BaseModel):
    name: str
    last_event_ts: Optional[float] = None
    status: str
    events_24h: int

class IngestStatus(BaseModel):
    connectors: List[IngestConnectorStatus]
    generated_ts: float

class GateArtifacts(BaseModel):
    status: str
    path: Optional[str] = None
    size: Optional[int] = None
    head: Optional[str] = None

class GateCounts(BaseModel):
    assets: Optional[int]
    vulnerabilities: Optional[int]
    findings: Optional[int]

class GateStatus(BaseModel):
    generated_ts: float
    artifacts: Dict[str, GateArtifacts]
    counts: GateCounts
    anomaly_model_ready: bool
    variance_ok: bool

class IRToken(BaseModel):
    raw: str
    normalized: str
    tag: str

class IRMeta(BaseModel):
    confidence: float
    fallback_used: bool
    tokens: List[IRToken] = Field(default_factory=list)
    unparsed_tokens: List[str] = Field(default_factory=list)

class IRClause(BaseModel):
    type: str
    operator: Optional[str] = None
    field: Optional[str] = None
    direction: Optional[str] = None
    value: Optional[Union[str, int, float, bool]] = None
    values: Optional[List[Union[str, int, float]]] = None

class NLPIR(BaseModel):
    domain: str
    clauses: List[IRClause]
    meta: IRMeta

class NLPPreview(BaseModel):
    count: int
    items: List[Dict[str, Any]]

class NLPQueryResponse(BaseModel):
    ir: NLPIR
    preview: NLPPreview
    elapsed_ms: float

__all__ = [
    'DashboardSnapshot','IngestStatus','GateStatus','NLPQueryResponse'
]
