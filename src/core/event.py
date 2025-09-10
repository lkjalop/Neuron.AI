"""Event schema and validation utilities.
Includes tenant-aware, versioned event contract.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, List
import time, uuid

EVENT_VERSION = "1.0"
REQUIRED_FIELDS = ["event_type", "timestamp"]

@dataclass
class Event:
    # Make key identifiers optional for easier test construction; auto-generate where absent
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: time.time())
    event_type: str = "generic"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: Optional[str] = None
    source: Optional[str] = None
    severity: Optional[float] = None
    pid: Optional[int] = None
    uid: Optional[int] = None
    process_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, Any] = field(default_factory=dict)  # ground_truth / predictions
    version: str = EVENT_VERSION

    def __post_init__(self):
        # If code used an outdated signature with 'raw' kwarg we merge it into metadata via instance attribute
        raw_dict = getattr(self, 'raw', None)
        if isinstance(raw_dict, dict):  # type: ignore[attr-defined]
            for k, v in raw_dict.items():
                self.metadata.setdefault(k, v)
            try:
                delattr(self, 'raw')  # type: ignore[attr-defined]
            except Exception:
                pass

    # Support legacy construction with unexpected kwargs (e.g., raw) via factory
    def __init__(self, *args, **kwargs):  # type: ignore[override]
        if args:
            # Fallback to dataclass default init if positional used
            super().__setattr__('event_id', args[0])  # not typical; minimal support
        # Extract known fields; allow omission
        event_id = kwargs.pop('event_id', str(uuid.uuid4()))
        timestamp = kwargs.pop('timestamp', time.time())
        event_type = kwargs.pop('event_type', 'generic')
        trace_id = kwargs.pop('trace_id', str(uuid.uuid4()))
        tenant_id = kwargs.pop('tenant_id', None)
        source = kwargs.pop('source', None)
        severity = kwargs.pop('severity', None)
        pid = kwargs.pop('pid', None)
        uid = kwargs.pop('uid', None)
        process_name = kwargs.pop('process_name', None)
        metadata = kwargs.pop('metadata', {}) or {}
        raw = kwargs.pop('raw', None)
        features = kwargs.pop('features', {}) or {}
        labels = kwargs.pop('labels', {}) or {}
        version = kwargs.pop('version', EVENT_VERSION)
        # Assign
        super().__setattr__('event_id', event_id)
        super().__setattr__('timestamp', timestamp)
        super().__setattr__('event_type', event_type)
        super().__setattr__('trace_id', trace_id)
        super().__setattr__('tenant_id', tenant_id)
        super().__setattr__('source', source)
        super().__setattr__('severity', severity)
        super().__setattr__('pid', pid)
        super().__setattr__('uid', uid)
        super().__setattr__('process_name', process_name)
        # Merge raw into metadata if provided
        if isinstance(raw, dict):
            md = dict(metadata)
            for k, v in raw.items():
                md.setdefault(k, v)
            metadata = md
        super().__setattr__('metadata', metadata)
        super().__setattr__('features', features)
        super().__setattr__('labels', labels)
        super().__setattr__('version', version)

    @staticmethod
    def create(event_type: str, *, tenant_id: Optional[str] = None, **kwargs) -> "Event":
        ts = kwargs.pop("timestamp", time.time())
        return Event(
            event_id=str(uuid.uuid4()),
            timestamp=ts,
            event_type=event_type,
            tenant_id=tenant_id,
            **kwargs,
        )

class EventValidationError(ValueError):
    pass

def validate_event(e: Event) -> None:
    missing = [f for f in REQUIRED_FIELDS if getattr(e, f, None) is None]
    if missing:
        raise EventValidationError(f"Missing required fields: {missing}")
    if e.timestamp > time.time() + 5:  # 5s future skew guard
        raise EventValidationError("Timestamp too far in future")
    if e.severity is not None and not (0 <= e.severity <= 100):
        raise EventValidationError("Severity outside 0-100")


def event_to_dict(e: Event) -> Dict[str, Any]:
    return asdict(e)


def dict_to_event(d: Dict[str, Any]) -> Event:
    # Accept legacy keys 'raw' or 'meta' mapping into metadata
    data = dict(d)
    if 'metadata' not in data:
        meta_accum: Dict[str, Any] = {}
        if 'raw' in data and isinstance(data['raw'], dict):
            meta_accum.update(data['raw'])
            data.pop('raw')
        if 'meta' in data and isinstance(data['meta'], dict):
            meta_accum.update(data['meta'])
            data.pop('meta')
        if meta_accum:
            data['metadata'] = meta_accum
    # Ensure required fields
    if 'event_id' not in data:
        data['event_id'] = str(uuid.uuid4())
    if 'timestamp' not in data:
        data['timestamp'] = time.time()
    if 'event_type' not in data:
        data['event_type'] = 'generic'
    return Event(**data)

