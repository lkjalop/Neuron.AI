"""Policy Context Provider

Supplies contextual metadata for anomalies/insights (e.g., asset criticality,
user role risk tier) to enrich downstream scoring or routing.
Currently a stub with in-memory maps; future: fetch from CMDB / IAM / graph.
"""
from __future__ import annotations

from typing import Dict, Any


class PolicyContextProvider:
    def __init__(self):
        self.asset_criticality: Dict[str, int] = {}
        self.user_risk: Dict[str, int] = {}

    def set_asset(self, asset: str, criticality: int):
        self.asset_criticality[asset] = int(criticality)

    def set_user(self, user: str, risk: int):
        self.user_risk[user] = int(risk)

    def enrich(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(payload)
        asset = payload.get("asset")
        user = payload.get("user") or payload.get("username")
        if asset and asset in self.asset_criticality:
            out["asset_criticality"] = self.asset_criticality[asset]
        if user and user in self.user_risk:
            out["user_risk"] = self.user_risk[user]
        return out

__all__ = ["PolicyContextProvider"]
