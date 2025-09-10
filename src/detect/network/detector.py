"""Simple network flow anomaly detector (Phase 1 network + risk overlay).

Heuristic approach (fast win):
 - Compute lightweight features from rolling asset stats (see state.py)
 - Flag anomaly if any rapid deviation heuristics fire:
    * byte ratio extreme (>8 or <0.125)
    * unique external hosts spike (>25 in short window) with high out ratio
    * unique ports spike (>30)
 - Assign a normalized score combining triggered conditions.

Enrichment:
 - If risk scoring available for asset (via vuln_store criticality or asset_metadata), overlay as risk_score field.

Output record fields:
  detector: "network"
  type: network_flow
  asset_id, features, score, risk_score, risk_severity
"""
from __future__ import annotations
from typing import List, Dict, Any
import time
from core.event import Event
from core.detect.interface import DetectionResult
from detect.network.state import net_state
from config import runtime_params
from core import metrics

# Risk overlay helpers (best-effort)
async def _lookup_asset_risk(asset_id: str | None):  # pragma: no cover - IO wrapper
    if not asset_id:
        return None, None
    try:
        from storage import vuln_store  # type: ignore
    except Exception:
        return None, None
    try:
        pg = vuln_store.postgres  # type: ignore[attr-defined]
        rows = await pg.fetch("SELECT criticality, external_exposure FROM assets WHERE id=$1", asset_id)  # type: ignore
        if rows:
            r = rows[0]
            crit = r.get("criticality") or 0.0
            ext = 1.0 if r.get("external_exposure") else 0.0
            # Simple composite -> risk score base (0-1) then scale to 0-100
            base = min(1.0, 0.7 * crit + 0.3 * ext)
            sev = "low"
            if base >= 0.7:
                sev = "high"
            elif base >= 0.4:
                sev = "medium"
            return base * 100.0, sev
    except Exception:
        return None, None
    return None, None

class NetworkFlowDetector:
    name = "network"

    def __init__(self):
        self._last_emit: dict[str, float] = {}
        self._recent: list[dict] = []  # ring buffer
        self._recent_max = 500

    def _flow_from_event(self, ev: Event) -> Dict[str, Any] | None:
        if ev.source not in ("flow", "net", "network"):
            return None
        md = ev.metadata or {}
        # Normalized minimal flow schema extraction
        rec = {
            "src_ip": md.get("src_ip") or md.get("src") or md.get("client_ip"),
            "dst_ip": md.get("dst_ip") or md.get("dst") or md.get("server_ip"),
            "src_port": md.get("src_port"),
            "dst_port": md.get("dst_port"),
            "protocol": md.get("proto") or md.get("protocol"),
            "bytes_in": md.get("bytes_in") or md.get("in_bytes") or 0,
            "bytes_out": md.get("bytes_out") or md.get("out_bytes") or 0,
            "duration": md.get("duration") or md.get("dur") or 0.0,
            "direction": md.get("direction") or ("out" if md.get("initiator") == "internal" else "in"),
            "dst_host": md.get("dst_host") or md.get("domain"),
            "src_host": md.get("src_host"),
            "is_external": bool(md.get("is_external") or md.get("external")),
        }
        return rec

    def process(self, event: Event) -> List[DetectionResult]:
        start_t = time.perf_counter()
        rec = self._flow_from_event(event)
        if rec is None:
            return []
        # Associate asset id (best-effort from labels or metadata)
        asset_id = event.labels.get("asset_id") if isinstance(event.labels, dict) else None
        if not asset_id:
            asset_id = event.metadata.get("asset_id") if isinstance(event.metadata, dict) else None
        state = net_state()
        stats = state.update(asset_id, rec)
        feats = stats.to_features()
        # Simple heuristic triggers
        triggers: list[str] = []
        # Use per-flow ratio for triggering (cumulative ratio can dilute anomalies over time)
        try:
            flow_byte_ratio = (float(rec.get("bytes_out",0))+1) / (float(rec.get("bytes_in",0))+1)
        except Exception:
            flow_byte_ratio = feats.get("net_byte_ratio", 1.0)
        byte_ratio = flow_byte_ratio
        # Trigger on extreme outbound/inbound ratio OR its inverse (defensive)
        try:
            inv_ratio = (1.0/byte_ratio) if byte_ratio != 0 else 0.0
        except Exception:
            inv_ratio = 0.0
        if byte_ratio > 8 or byte_ratio < 0.125 or inv_ratio > 8:
            triggers.append("byte_ratio")
        if feats["net_unique_external_hosts"] > 25 and byte_ratio > 2:
            triggers.append("external_host_spike")
        if feats["net_unique_ports"] > 30:
            triggers.append("port_spike")
        if not triggers:
            # record latency even if not anomalous (for baseline distribution)
            try:
                tenant_lbl = event.tenant_id or "global"
                metrics.NETWORK_DETECT_LATENCY_SECONDS.labels(tenant_lbl).observe(time.perf_counter() - start_t)  # type: ignore[attr-defined]
                # update assets tracked gauge lazily on non-empty state
                metrics.NETWORK_ASSETS_TRACKED.set(len(state._by_asset))  # type: ignore[attr-defined]
            except Exception:
                pass
            return []
        # Metrics per trigger + aggregate
        try:
            tenant_lbl = event.tenant_id or "global"
            metrics.NETWORK_ANOMALIES_TOTAL.labels(tenant=tenant_lbl, trigger="__total__").inc()  # type: ignore[attr-defined]
            for trig in triggers:
                metrics.NETWORK_ANOMALIES_TOTAL.labels(tenant=tenant_lbl, trigger=trig).inc()  # type: ignore[attr-defined]
            metrics.NETWORK_DETECT_LATENCY_SECONDS.labels(tenant_lbl).observe(time.perf_counter() - start_t)  # type: ignore[attr-defined]
            metrics.NETWORK_ASSETS_TRACKED.set(len(state._by_asset))  # type: ignore[attr-defined]
        except Exception:
            pass
        raw_score = min(1.0, 0.3 * len(triggers) + 0.1 * (feats["net_unique_external_hosts"] / 50))
        # Weight scaling with runtime param multiplier
        try:
            mult = float(runtime_params.get_param("detection.network.score_multiplier") or 1.0)
        except Exception:
            mult = 1.0
        score = max(0.0, min(1.0, raw_score * mult))
        out: DetectionResult = DetectionResult(
            detector=self.name,
            type="network_flow",
            asset_id=asset_id,
            features={k: round(v, 5) if isinstance(v, float) else v for k, v in feats.items()},
            triggers=triggers,
            score=score,
            normalized_score=score,
            ts=time.time(),
        )
        # Risk overlay (async lookups aren't available in sync interface; attach placeholder)
        out["risk_score"] = None
        out["risk_severity"] = None
        # Ring buffer store (best-effort)
        try:
            self._recent.append(dict(out))
            if len(self._recent) > self._recent_max:
                del self._recent[:-self._recent_max]
        except Exception:
            pass
        return [out]

# Registration helper
_registered = False

def register_network():  # pragma: no cover - trivial
    global _registered
    if _registered:
        return
    from core.detect.interface import registry
    registry.register(NetworkFlowDetector())
    _registered = True

__all__ = ["register_network", "NetworkFlowDetector"]
