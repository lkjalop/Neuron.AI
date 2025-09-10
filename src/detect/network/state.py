"""Lightweight in-memory state for network flow feature extraction.

Tracks per-asset (or per-IP) rolling stats for:
 - first_seen_ts
 - last_seen_ts
 - distinct_external_hosts
 - distinct_ports
 - total_bytes_in/out
 - flow_count

Provides helpers to update stats from a normalized flow record.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Any
import time

@dataclass
class AssetNetStats:
    asset_id: str | None
    first_seen: float = field(default_factory=lambda: time.time())
    last_seen: float = field(default_factory=lambda: time.time())
    distinct_external_hosts: Set[str] = field(default_factory=set)
    distinct_ports: Set[int] = field(default_factory=set)
    total_bytes_in: int = 0
    total_bytes_out: int = 0
    flow_count: int = 0

    def update(self, rec: dict):
        now = time.time()
        self.last_seen = now
        self.flow_count += 1
        ext_host = rec.get("dst_host") if rec.get("direction") == "out" else rec.get("src_host")
        if ext_host and rec.get("is_external"):
            self.distinct_external_hosts.add(str(ext_host))
        port = rec.get("dst_port") if rec.get("direction") == "out" else rec.get("src_port")
        if isinstance(port, int):
            self.distinct_ports.add(port)
        self.total_bytes_in += int(rec.get("bytes_in", 0))
        self.total_bytes_out += int(rec.get("bytes_out", 0))

    def to_features(self) -> dict:
        dur = max(self.last_seen - self.first_seen, 1.0)
        return {
            "net_flow_rate": self.flow_count / dur,
            "net_unique_external_hosts": len(self.distinct_external_hosts),
            "net_unique_ports": len(self.distinct_ports),
            "net_bytes_in": self.total_bytes_in,
            "net_bytes_out": self.total_bytes_out,
            "net_byte_ratio": (self.total_bytes_out + 1) / (self.total_bytes_in + 1),
        }

class NetworkState:
    def __init__(self):
        self._by_asset: Dict[str, AssetNetStats] = {}

    def update(self, asset_id: str | None, rec: dict) -> AssetNetStats:
        key = asset_id or rec.get("src_ip") or rec.get("dst_ip") or "unknown"
        stats = self._by_asset.get(key)
        if stats is None:
            stats = AssetNetStats(asset_id=asset_id)
            self._by_asset[key] = stats
        stats.update(rec)
        return stats

    def snapshot(self) -> Dict[str, dict]:  # diagnostics
        return {k: v.to_features() for k, v in self._by_asset.items()}

_state: NetworkState | None = None

def net_state() -> NetworkState:
    global _state
    if _state is None:
        _state = NetworkState()
    return _state

__all__ = ["net_state", "NetworkState", "AssetNetStats"]
