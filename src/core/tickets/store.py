"""Ticket store and persistence layer (Phase 6.1).

Lightweight in-memory store with JSONL append persistence + rotation.
Rotation strategy copies case persistence approach (size + line count thresholds) but kept
independent to avoid coupling concerns.
"""
from __future__ import annotations
import time, json, os, threading, hashlib, typing as t, pathlib
from dataclasses import dataclass, asdict
from config import runtime_params
from core import metrics
from prometheus_client import REGISTRY as _PROM_REGISTRY  # type: ignore

TICKET_FILE = pathlib.Path("artifacts/tickets/tickets.jsonl")
TICKET_FILE.parent.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 5_000_000
MAX_LINES = 20000
_ROT_LOCK = threading.Lock()
_STORE_LOCK = threading.Lock()

TicketStatus = t.Literal["open","ack","in_progress","blocked","closed"]

@dataclass
class Ticket:
    id: str
    case_id: str | None
    status: TicketStatus
    severity: str  # low|medium|high|critical
    priority: int  # 1 (highest) .. 5
    source: str  # auto|manual|system
    created_ts: float
    updated_ts: float
    sla_due_ts: float
    tags: list[str]
    assignees: list[str]
    comments: list[dict]
    breached: bool = False

    def to_record(self) -> dict:
        d = asdict(self)
        return d

_store: dict[str, Ticket] = {}
_index_tag: dict[str, set[str]] = {}
_index_severity: dict[str, set[str]] = {}
_index_assignee: dict[str, set[str]] = {}
_index_breached: set[str] = set()

# Initialize gauges for all statuses to ensure presence in /metrics even before first ticket
for _st in ["open","ack","in_progress","blocked","closed"]:
    try:
        metrics.TICKETS_TOTAL.labels(status=_st).inc(0)
    except Exception:
        pass
try:  # ensure transitions counter appears in scrape even before first real transition
    metrics.TICKET_TRANSITIONS_TOTAL.labels(from_status="open", to_status="ack").inc(0)
    # also add a synthetic closed path with zero to ensure multiple label families present
    metrics.TICKET_TRANSITIONS_TOTAL.labels(from_status="in_progress", to_status="closed").inc(0)
    # force registration in default registry if it was cleared
    try:
        from prometheus_client import REGISTRY as _REG
        if getattr(_REG, '_names_to_collectors', None) is not None:
            if 'neuron_ticket_transitions_total' not in getattr(_REG, '_names_to_collectors'):
                _REG.register(metrics.TICKET_TRANSITIONS_TOTAL)
    except Exception:
        pass
except Exception:
    pass

def _ensure_registered(obj):  # best-effort re-registration (tests may clear registry)
    try:
        # Collector exposes ._name or ._metric_family_name depending on type; rely on exception if already registered.
        if hasattr(_PROM_REGISTRY, '_names_to_collectors'):
            # If cleared, the name won't be present.
            name = getattr(obj, '_name', None) or getattr(obj, '_metric_family_name', None)
            if name and name not in getattr(_PROM_REGISTRY, '_names_to_collectors', {}):  # type: ignore
                _PROM_REGISTRY.register(obj)
    except Exception:
        pass


def _rotate_if_needed():  # best-effort
    try:
        if not TICKET_FILE.exists():
            return
        sz = TICKET_FILE.stat().st_size
        lines = sum(1 for _ in TICKET_FILE.open())
        if sz < MAX_BYTES and lines < MAX_LINES:
            return
        # rotate: tickets.jsonl.1 -> .2, etc (keep 2 history files max for now)
        for idx in range(2,0,-1):
            src = TICKET_FILE.parent / f"tickets.jsonl.{idx}"
            dst = TICKET_FILE.parent / f"tickets.jsonl.{idx+1}"
            if src.exists():
                if idx+1 > 3:
                    try: dst.unlink()
                    except Exception: pass
                else:
                    src.rename(dst)
        TICKET_FILE.rename(TICKET_FILE.parent / "tickets.jsonl.1")
    except Exception:
        pass

def _persist(ticket: Ticket):  # best-effort
    try:
        with _ROT_LOCK:
            _rotate_if_needed()
        with TICKET_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ticket.to_record(), sort_keys=True) + "\n")
    except Exception:
        pass


def _gen_id(case_id: str | None) -> str:
    raw = f"{case_id or ''}:{time.time_ns()}:{os.getpid()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def create_ticket(case_id: str | None, severity: str, priority: int, source: str = "manual", tags: list[str] | None = None, assignees: list[str] | None = None) -> Ticket:
    now = time.time()
    sla_seconds = int(runtime_params.get_param("ticket.sla.seconds") or 3600)
    t = Ticket(
        id=_gen_id(case_id),
        case_id=case_id,
        status="open",
        severity=severity,
        priority=priority,
        source=source,
        created_ts=now,
        updated_ts=now,
        sla_due_ts=now + sla_seconds,
        tags=tags or [],
        assignees=assignees or [],
        comments=[],
    )
    with _STORE_LOCK:
        _store[t.id] = t
        # index updates
        _index_severity.setdefault(severity, set()).add(t.id)
        for tg in t.tags:
            _index_tag.setdefault(tg, set()).add(t.id)
        for a in t.assignees:
            _index_assignee.setdefault(a, set()).add(t.id)
    _ensure_registered(metrics.TICKETS_TOTAL)
    _ensure_registered(metrics.TICKET_TRANSITIONS_TOTAL)
    metrics.TICKETS_TOTAL.labels(status=t.status).inc()
    _persist(t)
    return t


def get_ticket(ticket_id: str) -> Ticket | None:
    return _store.get(ticket_id)


def list_tickets(status: str | None = None, case_id: str | None = None) -> list[Ticket]:
    out = list(_store.values())
    if status:
        out = [t for t in out if t.status == status]
    if case_id:
        out = [t for t in out if t.case_id == case_id]
    # newest first
    return sorted(out, key=lambda x: x.created_ts, reverse=True)

def advanced_filter(tag: str | None = None, severity: str | None = None, assignee: str | None = None, breached: bool | None = None, updated_since: float | None = None) -> list[Ticket]:
    """Return tickets satisfying all provided filters (intersection on indexes where possible)."""
    candidate_ids: set[str] | None = None
    # Index-based narrowing
    if tag:
        candidate_ids = set(_index_tag.get(tag, set()))
    if severity:
        ids = _index_severity.get(severity, set())
        candidate_ids = ids if candidate_ids is None else candidate_ids & ids
    if assignee:
        ids = _index_assignee.get(assignee, set())
        candidate_ids = ids if candidate_ids is None else candidate_ids & ids
    if breached is not None:
        ids = _index_breached if breached else (set(_store.keys()) - _index_breached)
        candidate_ids = ids if candidate_ids is None else candidate_ids & ids
    # Fallback: if no index used, start with all
    if candidate_ids is None:
        candidate_list = list(_store.values())
    else:
        candidate_list = [ _store[i] for i in candidate_ids if i in _store ]
    # Time filter
    if updated_since is not None:
        try:
            us = float(updated_since)
            candidate_list = [t for t in candidate_list if t.updated_ts >= us]
        except Exception:
            pass
    # Sort newest first
    return sorted(candidate_list, key=lambda x: x.created_ts, reverse=True)

_ALLOWED_TRANSITIONS = {
    "open": {"ack","in_progress","blocked","closed"},
    "ack": {"in_progress","blocked","closed"},
    "in_progress": {"blocked","closed"},
    "blocked": {"in_progress","closed"},
    "closed": set(),
}

def update_ticket(ticket_id: str, *, status: str | None = None, add_comment: dict | None = None, add_tags: list[str] | None = None, assignees: list[str] | None = None) -> Ticket | None:
    with _STORE_LOCK:
        t = _store.get(ticket_id)
        if not t:
            return None
        if status and status != t.status:
            if status not in _ALLOWED_TRANSITIONS.get(t.status, set()):
                raise ValueError(f"illegal transition {t.status}->{status}")
            _ensure_registered(metrics.TICKET_TRANSITIONS_TOTAL)
            metrics.TICKET_TRANSITIONS_TOTAL.labels(from_status=t.status, to_status=status).inc()
            # decrement old gauge, increment new gauge
            try:
                _ensure_registered(metrics.TICKETS_TOTAL)
                metrics.TICKETS_TOTAL.labels(status=t.status).dec()
                metrics.TICKETS_TOTAL.labels(status=status).inc()
            except Exception:
                pass
            t.status = status  # type: ignore
        if add_comment:
            c = {"ts": time.time(), **add_comment}
            t.comments.append(c)
        if add_tags:
            for tag in add_tags:
                if tag not in t.tags:
                    t.tags.append(tag)
                    _index_tag.setdefault(tag, set()).add(t.id)
        if assignees is not None:
            # remove old assignees
            for a in set(t.assignees):
                try:
                    _index_assignee.get(a, set()).discard(t.id)
                except Exception:
                    pass
            t.assignees = assignees
            for a in t.assignees:
                _index_assignee.setdefault(a, set()).add(t.id)
        t.updated_ts = time.time()
        # breached tracking
        if t.breached:
            _index_breached.add(t.id)
        else:
            _index_breached.discard(t.id)
        _persist(t)
        return t


def scan_sla():
    now = time.time()
    with _STORE_LOCK:
        for t in _store.values():
            if not t.breached and now > t.sla_due_ts and t.status != "closed":
                t.breached = True
                try:
                    metrics.TICKET_SLA_BREACH_TOTAL.labels(severity=t.severity).inc()
                except Exception:
                    pass

__all__ = [
    "Ticket",
    "create_ticket",
    "get_ticket",
    "list_tickets",
    "update_ticket",
    "scan_sla",
    "advanced_filter",
]
