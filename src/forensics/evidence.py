"""Forensics Evidence Bundler & Timeline Exporter.

Produces case directories with:
 - anomalies.jsonl (all anomalies associated to case)
 - timeline.jsonl (sorted events for involved entities)

Case derivation strategy (initial heuristic):
 - Group anomalies by (tenant_id, detector) within time window (default 120s)
 - Merge groups sharing at least one event_id or entity (user/process name if present)

Lightweight; can be replaced by graph-based correlation later.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Iterable, Optional, Set
import pathlib, json, time, uuid

from core.event import Event
from detect.orchestrator import Anomaly


@dataclass
class Case:
    case_id: str
    tenant_id: str
    detectors: Set[str]
    first_ts: float
    last_ts: float
    anomaly_count: int
    entities: Set[str]

    def to_dict(self):
        return {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "detectors": sorted(self.detectors),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "anomaly_count": self.anomaly_count,
            "entities": sorted(self.entities),
        }


class EvidenceBundler:
    def __init__(self, root: pathlib.Path | str = "artifacts/forensics", window_s: int = 120):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.window_s = window_s

    def _entity_keys(self, event: Event) -> List[str]:
        out: List[str] = []
        if event.process_name:
            out.append(f"proc:{event.process_name}")
        if event.uid is not None:
            out.append(f"uid:{event.uid}")
        if event.pid is not None:
            out.append(f"pid:{event.pid}")
        return out or [f"event:{event.event_id}"]

    def bundle(self, events: Iterable[Event], anomalies: Iterable[Anomaly]) -> List[Case]:
        events_by_id: Dict[str, Event] = {e.event_id: e for e in events}
        # Group anomalies by coarse time bucket + tenant
        groups: Dict[str, List[Anomaly]] = {}
        for a in anomalies:
            bucket = int(a.ts // self.window_s)
            key = f"{a.tenant_id or 'global'}:{bucket}"
            groups.setdefault(key, []).append(a)
        preliminary: List[Case] = []
        bucket_entities: Dict[str, Set[str]] = {}
        bucket_anomalies: Dict[str, List[Anomaly]] = {}
        for key, group in groups.items():
            tenant = key.split(':', 1)[0]
            detectors = {a.detector for a in group}
            ts_list = [a.ts for a in group]
            entity_accum: Set[str] = set()
            for a in group:
                ev = events_by_id.get(a.event_id)
                if ev:
                    entity_accum.update(self._entity_keys(ev))
            bucket_entities[key] = entity_accum
            bucket_anomalies[key] = group
            preliminary.append(Case(
                case_id=str(uuid.uuid4()),
                tenant_id=tenant,
                detectors=detectors,
                first_ts=min(ts_list),
                last_ts=max(ts_list),
                anomaly_count=len(group),
                entities=entity_accum,
            ))
        # Merge adjacent buckets (same tenant) if entity intersection non-empty
        merged: List[Case] = []
        preliminary.sort(key=lambda c: (c.tenant_id, c.first_ts))
        current: Optional[Case] = None
        current_keys: List[str] = []
        for case in preliminary:
            if current is None:
                current = case
                current_keys = [self._bucket_key(case.tenant_id, int(case.first_ts // self.window_s))]
                continue
            same_tenant = case.tenant_id == current.tenant_id
            adjacent = int(case.first_ts // self.window_s) <= int(current.last_ts // self.window_s) + 1
            if same_tenant and adjacent and (case.entities & current.entities):
                # Merge
                current.detectors.update(case.detectors)
                current.entities.update(case.entities)
                current.first_ts = min(current.first_ts, case.first_ts)
                current.last_ts = max(current.last_ts, case.last_ts)
                current.anomaly_count += case.anomaly_count
                current_keys.append(self._bucket_key(case.tenant_id, int(case.first_ts // self.window_s)))
            else:
                merged.append(current)
                current = case
                current_keys = [self._bucket_key(case.tenant_id, int(case.first_ts // self.window_s))]
        if current:
            merged.append(current)
        # Persist merged cases using concatenated anomalies from underlying buckets
        out_cases: List[Case] = []
        for m in merged:
            # gather anomaly lists for all buckets overlapping time range & tenant & entities
            bucket_ids = []
            start_bucket = int(m.first_ts // self.window_s)
            end_bucket = int(m.last_ts // self.window_s)
            for b in range(start_bucket, end_bucket + 1):
                bucket_ids.append(self._bucket_key(m.tenant_id, b))
            combined_anoms: List[Anomaly] = []
            for bid in bucket_ids:
                combined_anoms.extend(bucket_anomalies.get(bid, []))
            self._persist_case(m, combined_anoms, events_by_id)
            out_cases.append(m)
        return out_cases

    def _bucket_key(self, tenant: str, bucket: int) -> str:
        return f"{tenant}:{bucket}"

    def _persist_case(self, case: Case, anomalies: List[Anomaly], events_by_id: Dict[str, Event]):
        cdir = self.root / f"case_{case.case_id}"
        cdir.mkdir(parents=True, exist_ok=True)
        # Anomalies
        with (cdir / 'anomalies.jsonl').open('w', encoding='utf-8') as f:
            for a in anomalies:
                f.write(json.dumps(a.to_dict()) + "\n")
        # Timeline events: gather unique events referenced by anomalies + simple chronological order
        timeline_events = []
        for a in anomalies:
            ev = events_by_id.get(a.event_id)
            if ev:
                timeline_events.append(ev)
        timeline_events.sort(key=lambda e: e.timestamp)
        with (cdir / 'timeline.jsonl').open('w', encoding='utf-8') as f:
            for ev in timeline_events:
                f.write(json.dumps({
                    "event_id": ev.event_id,
                    "timestamp": ev.timestamp,
                    "event_type": ev.event_type,
                    "severity": ev.severity,
                    "process_name": ev.process_name,
                    "tenant_id": ev.tenant_id,
                }) + "\n")
        # Summary metadata
        with (cdir / 'case.json').open('w', encoding='utf-8') as f:
            json.dump(case.to_dict(), f, indent=2)


__all__ = ["EvidenceBundler", "Case"]
