"""Behavioral & network detectors (Batch 5 scaffold).

Heuristic, lightweight detectors generating minimal anomaly records with fields:
  - detector: name
  - score: float heuristic score (0-1 rough)
  - reason: short string
  - metadata: auxiliary values

These will later be enriched with MITRE technique references.
"""
from __future__ import annotations
from typing import List
import time, math
from config import runtime_params  # runtime param access (best-effort)
from core import metrics  # to expose anomaly counters
try:  # ensure counter exists (define dynamically if metrics exposes registry pattern)
    if not hasattr(metrics, 'DETECTOR_ANOMALIES_TOTAL'):
        from prometheus_client import Counter  # type: ignore
        metrics.DETECTOR_ANOMALIES_TOTAL = Counter('neuron_detector_anomalies_total', 'Anomalies emitted by detectors', ['detector','reason'])  # type: ignore
except Exception:
    class _Dummy:
        def labels(self, **kwargs):
            return self
        def inc(self, *a, **k):
            return None
    metrics.DETECTOR_ANOMALIES_TOTAL = _Dummy()  # type: ignore
from core.event import Event
from config.detectors import (
    LATERAL_THRESHOLD_DEFAULT, LATERAL_TTL_SECONDS_DEFAULT, LATERAL_MAX_USERS_DEFAULT,
    BEACON_MIN_INTERVALS_DEFAULT, BEACON_MAX_INTERVALS_DEFAULT, BEACON_TTL_SECONDS_DEFAULT, BEACON_JITTER_RATIO_DEFAULT, BEACON_MAX_AVG_INTERVAL_DEFAULT, BEACON_MAX_FLOWS_DEFAULT,
    DNS_MIN_LABEL_LEN_DEFAULT, DNS_MIN_UNIQUE_RATIO_DEFAULT,
    PERSISTENCE_PARENTS_DEFAULT, PERSISTENCE_TARGETS_DEFAULT,
)
from .interface import DetectionResult, registry


class LateralMovementDetector:
    name = "lateral_movement"

    def __init__(self):
        # Track (src_user -> {dest_ip -> first_seen_ts}) for TTL pruning
        self._user_dests: dict[str, dict[str, float]] = {}
        self._last_prune = time.time()

    def process(self, event: Event) -> List[DetectionResult]:
        meta = getattr(event, 'metadata', {}) or {}
        raw = meta.get('raw') or {}
        src_user = raw.get('user') or meta.get('user')
        dst_ip = raw.get('dst_ip') or raw.get('dest_ip') or meta.get('dst_ip')
        if not (src_user and dst_ip):
            return []
        record = self._user_dests.setdefault(src_user, {})
        pre = len(record)
        # TTL & threshold parameters
        ttl = LATERAL_TTL_SECONDS_DEFAULT
        threshold = LATERAL_THRESHOLD_DEFAULT
        try:
            if runtime_params:
                tv = runtime_params.get_param("detector.lateral.ttl_seconds")
                if isinstance(tv, (int, float)) and tv > 0:
                    ttl = float(tv)
                thv = runtime_params.get_param("detector.lateral.threshold")
                if isinstance(thv, (int, float)) and thv > 0:
                    threshold = int(thv)
        except Exception:
            pass
        now = time.time()
        # prune expired per-user
        for ip, ts in list(record.items()):
            if now - ts > ttl:
                record.pop(ip, None)
        record.setdefault(dst_ip, now)
        post = len(record)
        if post >= threshold and post > pre:
            score = min(1.0, (post - threshold + 1) / max(1, threshold))
            anom = DetectionResult(detector=self.name, score=score, reason="many_new_destinations", metadata={"user": src_user, "distinct_dests": post})
            try:
                metrics.DETECTOR_ANOMALIES_TOTAL.labels(detector=self.name, reason="many_new_destinations").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
            return [anom]
        # global periodic prune (cap memory)
        # Guardrail max users map size
        max_users = LATERAL_MAX_USERS_DEFAULT
        try:
            if runtime_params:
                mu = runtime_params.get_param("detector.lateral.max_users")
                if isinstance(mu, (int,float)) and mu > 0:
                    max_users = int(mu)
        except Exception:
            pass
        if now - self._last_prune > 300 and len(self._user_dests) > max_users:
            # Drop oldest half by earliest ts across users (approximate)
            users_sorted = sorted(self._user_dests.items(), key=lambda kv: min(kv[1].values()) if kv[1] else now)
            for u, _ in users_sorted[: len(users_sorted)//2]:
                self._user_dests.pop(u, None)
            self._last_prune = now
        return []


class PersistenceDetector:
    name = "persistence"
    SUSPICIOUS_PARENTS = {"powershell.exe", "cmd.exe", "bash"}
    TARGET_PROCESSES = {"reg.exe", "schtasks.exe", "launchctl", "systemctl"}

    def process(self, event: Event) -> List[DetectionResult]:
        meta = getattr(event, 'metadata', {}) or {}
        raw = meta.get('raw') or {}
        proc = raw.get('process_name') or raw.get('process')
        parent = raw.get('parent_process') or raw.get('parent')
        cmd = raw.get('command_line') or meta.get('command_line')
        if not (proc and parent):
            return []
        # Param overrides
        suspicious_parents = set(PERSISTENCE_PARENTS_DEFAULT)
        targets = set(PERSISTENCE_TARGETS_DEFAULT)
        try:
            if runtime_params:
                sp = runtime_params.get_param("detector.persistence.parents")
                if isinstance(sp, list):
                    suspicious_parents = {str(x).lower() for x in sp if x}
                tp = runtime_params.get_param("detector.persistence.targets")
                if isinstance(tp, list):
                    targets = {str(x).lower() for x in tp if x}
        except Exception:
            pass
        if parent.lower() in suspicious_parents and proc.lower() in targets:
            score = 0.8
            reason = "suspicious_parent_child_combo"
            anom = DetectionResult(detector=self.name, score=score, reason=reason, metadata={"parent": parent, "proc": proc, "cmd": cmd})
            try:
                metrics.DETECTOR_ANOMALIES_TOTAL.labels(detector=self.name, reason=reason).inc()  # type: ignore[attr-defined]
            except Exception:
                pass
            return [anom]
        return []


class BeaconingDetector:
    name = "beaconing"

    def __init__(self):
        # track per (src_ip->dst_ip) timestamp deltas (circular buffer of last N intervals + last seen ts for TTL)
        self._flows: dict[tuple[str,str], list[float]] = {}
        self._last_ts: dict[tuple[str,str], float] = {}
        self._last_prune = time.time()

    def process(self, event: Event) -> List[DetectionResult]:
        meta = getattr(event, 'metadata', {}) or {}
        raw = meta.get('raw') or {}
        src = raw.get('src_ip')
        dst = raw.get('dst_ip') or raw.get('dest_ip')
        if not (src and dst):
            return []
        key = (src, dst)
        now = time.time()
        last = self._last_ts.get(key)
        self._last_ts[key] = now
        if last is None:
            return []
        interval = now - last
        buf = self._flows.setdefault(key, [])
        buf.append(interval)
        max_intervals = BEACON_MAX_INTERVALS_DEFAULT
        min_intervals = BEACON_MIN_INTERVALS_DEFAULT
        ttl = BEACON_TTL_SECONDS_DEFAULT
        jitter_ratio = BEACON_JITTER_RATIO_DEFAULT
        max_avg = BEACON_MAX_AVG_INTERVAL_DEFAULT
        try:
            if runtime_params:
                mv = runtime_params.get_param("detector.beacon.max_intervals")
                if isinstance(mv, (int,float)) and mv > 0:
                    max_intervals = int(mv)
                miv = runtime_params.get_param("detector.beacon.min_intervals")
                if isinstance(miv, (int,float)) and miv > 0:
                    min_intervals = int(miv)
                ttlv = runtime_params.get_param("detector.beacon.ttl_seconds")
                if isinstance(ttlv, (int,float)) and ttlv > 0:
                    ttl = float(ttlv)
                jr = runtime_params.get_param("detector.beacon.jitter_ratio")
                if isinstance(jr, (int,float)) and jr > 0:
                    jitter_ratio = float(jr)
                ma = runtime_params.get_param("detector.beacon.max_avg_interval")
                if isinstance(ma, (int,float)) and ma > 0:
                    max_avg = float(ma)
        except Exception:
            pass
        if len(buf) > max_intervals:
            buf.pop(0)
        if len(buf) < min_intervals:
            return []
        avg = sum(buf) / len(buf)
        variance = sum((i - avg)**2 for i in buf)/len(buf)
        std = math.sqrt(variance)
        # prune stale flows periodically
        if now - self._last_prune > 300:
            for k, ts in list(self._last_ts.items()):
                if now - ts > ttl:
                    self._last_ts.pop(k, None)
                    self._flows.pop(k, None)
            self._last_prune = now
        # heuristic: low jitter + small interval indicates potential beacon
        # Record interval metric pre-filter
        try:
            flow_label = f"{src}->{dst}"[:60]
            metrics.BEACON_INTERVAL_SECONDS.labels(tenant=meta.get('tenant_id','unknown'), flow=flow_label).observe(interval)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Guardrail for max flows
        max_flows = BEACON_MAX_FLOWS_DEFAULT
        try:
            if runtime_params:
                mf = runtime_params.get_param("detector.beacon.max_flows")
                if isinstance(mf, (int,float)) and mf > 0:
                    max_flows = int(mf)
        except Exception:
            pass
        if len(self._flows) > max_flows:
            # prune oldest by last timestamp
            flows_sorted = sorted(self._last_ts.items(), key=lambda kv: kv[1])
            for k2,_ts in flows_sorted[: len(flows_sorted)//4]:  # drop 25%
                self._flows.pop(k2, None)
                self._last_ts.pop(k2, None)
        if avg < max_avg and std < avg * jitter_ratio:
            score = min(1.0, (max_avg-avg)/max_avg + (jitter_ratio - std/avg))
            anom = DetectionResult(detector=self.name, score=score, reason="low_jitter_periodic_flow", metadata={"src": src, "dst": dst, "avg_interval_s": round(avg,2), "std": round(std,2)})
            try:
                metrics.DETECTOR_ANOMALIES_TOTAL.labels(detector=self.name, reason="low_jitter_periodic_flow").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
            return [anom]
        return []


class DNSTunnelingDetector:
    name = "dns_tunneling"

    def process(self, event: Event) -> List[DetectionResult]:
        meta = getattr(event, 'metadata', {}) or {}
        raw = meta.get('raw') or {}
        query = raw.get('query') or raw.get('fqdn')
        if not query:
            return []
        # heuristic: long label length or high entropy (approx: ratio of unique chars)
        label = query.split('.')[0]
        unique_ratio = len(set(label))/len(label) if label else 0.0
        min_len = DNS_MIN_LABEL_LEN_DEFAULT
        min_unique = DNS_MIN_UNIQUE_RATIO_DEFAULT
        try:
            if runtime_params:
                ml = runtime_params.get_param("detector.dns.min_label_len")
                if isinstance(ml, (int,float)) and ml > 0:
                    min_len = int(ml)
                mu = runtime_params.get_param("detector.dns.min_unique_ratio")
                if isinstance(mu, (int,float)) and 0 < mu < 1:
                    min_unique = float(mu)
        except Exception:
            pass
        if len(label) > min_len and unique_ratio > min_unique:
            score = min(1.0, (len(label)-min_len)/max(1,(min_len//2)) + (unique_ratio-min_unique))
            anom = DetectionResult(detector=self.name, score=score, reason="long_high_entropy_subdomain", metadata={"query": query, "label_len": len(label), "unique_ratio": round(unique_ratio,2)})
            try:
                metrics.DETECTOR_ANOMALIES_TOTAL.labels(detector=self.name, reason="long_high_entropy_subdomain").inc()  # type: ignore[attr-defined]
            except Exception:
                pass
            return [anom]
        return []


def register_behavioral_detectors():  # idempotent
    registry.register(LateralMovementDetector())
    registry.register(PersistenceDetector())
    registry.register(BeaconingDetector())
    registry.register(DNSTunnelingDetector())


# Auto-register on import (pipeline constructs usually import registry before detectors)
try:  # pragma: no cover - defensive
    register_behavioral_detectors()
except Exception:
    pass

__all__ = [
    'register_behavioral_detectors'
]