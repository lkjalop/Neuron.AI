"""Exposure Graph Builder (Batch 21).

Nodes:
  asset:<id>
  component:<id>
  vuln:<cve>
  technique:<technique_id>
  control:<control_id>

Edges (typed):
  asset->component
  component->vuln
  vuln->technique
  control->technique

Exploitability score:
  exploitability = base_risk * (1 - coverage_factor) * temporal_decay

Temporal decay:
  temporal_decay = 0.5 ** (age_days / half_life_days)  (runtime param risk.decay.half_life_days, default 30)

Snapshot persisted to artifacts/exposure_graph.json
"""
from __future__ import annotations

from typing import Dict, Any, List, Set
import time, json, math, pathlib
from dataclasses import dataclass, field

try:
  from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
  runtime_params = None  # type: ignore

try:
  from core import metrics  # type: ignore
except Exception:  # pragma: no cover
  metrics = None  # type: ignore

GRAPH_PATH = "artifacts/exposure_graph.json"


@dataclass
class Node:
  id: str
  type: str
  data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
  src: str
  dst: str
  type: str


class ExposureGraph:
  def __init__(self):
    self.nodes: Dict[str, Node] = {}
    self.edges: List[Edge] = []
    self.vuln_exploitability: Dict[str, float] = {}
    self.total_risk: float = 0.0

  def add_node(self, nid: str, ntype: str, **data):
    existing = self.nodes.get(nid)
    if existing:
      existing.data.update(data)
      return existing
    n = Node(id=nid, type=ntype, data=data)
    self.nodes[nid] = n
    return n

  def add_edge(self, src: str, dst: str, etype: str):
    self.edges.append(Edge(src=src, dst=dst, type=etype))

  def build(self, findings: List[Dict[str, Any]], controls: List[Dict[str, Any]]):
    # Control -> techniques map
    control_map: Dict[str, Set[str]] = {}
    for c in controls:
      cid = c.get("id") or c.get("control_id")
      if not cid:
        continue
      techs = c.get("techniques") or []
      tset = {t for t in techs if isinstance(t, str)}
      control_map[cid] = tset
      self.add_node(f"control:{cid}", "control", name=cid)
      for t in tset:
        self.add_node(f"technique:{t}", "technique")
        self.add_edge(f"control:{cid}", f"technique:{t}", "control-technique")
        if metrics and t:  # potential gap metric: no controls for technique will be counted later
          pass
    half_life = 30.0
    try:
      if runtime_params is not None:
        hv = runtime_params.get_param("risk.decay.half_life_days")
        if hv:
          half_life = float(hv)
    except Exception:
      pass
    now = time.time()
    total_risk = 0.0
    technique_control_index: Dict[str, int] = {}
    for cid, techs in control_map.items():
      for t in techs:
        technique_control_index[t] = technique_control_index.get(t, 0) + 1
    for f in findings:
      cve = f.get("cve_id") or f.get("id")
      if not cve:
        continue
      asset_id = f.get("asset_id")
      component_id = f.get("component_id")
      if asset_id:
        self.add_node(f"asset:{asset_id}", "asset")
      if component_id:
        self.add_node(f"component:{component_id}", "component")
      if asset_id and component_id:
        self.add_edge(f"asset:{asset_id}", f"component:{component_id}", "asset-component")
      severity = (f.get("risk_severity") or f.get("severity") or "MEDIUM").upper()
      base_risk = f.get("risk_score")
      if base_risk is None:
        sev_map = {"CRITICAL":0.95, "HIGH":0.75, "MEDIUM":0.5, "LOW":0.3}
        base_risk = sev_map.get(severity, 0.4)
      discovered_ts = f.get("first_seen") or f.get("created_at") or now
      try:
        age_days = max(0.0, (now - float(discovered_ts)) / 86400.0)
      except Exception:
        age_days = 0.0
      temporal_decay = 0.5 ** (age_days / max(1e-6, half_life))
      vuln_node = f"vuln:{cve}"
      self.add_node(vuln_node, "vuln", severity=severity, base_risk=base_risk, age_days=age_days)
      # Technique inference (placeholder): derive bucket from first char group
      technique_id = f"T-{cve[0:3].upper()}"
      self.add_node(f"technique:{technique_id}", "technique")
      self.add_edge(vuln_node, f"technique:{technique_id}", "vuln-technique")
      # Component linkage
      if component_id:
        self.add_edge(f"component:{component_id}", vuln_node, "component-vuln")
      ctrl_count = technique_control_index.get(technique_id, 0)
      coverage_factor = 1.0 if ctrl_count > 0 else 0.0
      exploitability = float(base_risk) * (1 - coverage_factor) * temporal_decay
      self.vuln_exploitability[vuln_node] = exploitability
      total_risk += exploitability
      if metrics and ctrl_count == 0:
        try:
          metrics.EXPOSURE_CONTROL_GAPS_TOTAL.labels(technique=technique_id).inc()  # type: ignore[attr-defined]
        except Exception:
          pass
    self.total_risk = total_risk
    if metrics:
      try:
        metrics.EXPOSURE_TOTAL_RISK.set(total_risk)  # type: ignore[attr-defined]
      except Exception:
        pass

  def snapshot(self) -> Dict[str, Any]:
    return {
      "nodes": [
        {"id": n.id, "type": n.type, **(n.data or {})} for n in self.nodes.values()
      ],
      "edges": [e.__dict__ for e in self.edges],
      "vuln_exploitability": self.vuln_exploitability,
      "total_risk": self.total_risk,
    }

  def persist(self, path: str = GRAPH_PATH) -> str:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
      json.dump(self.snapshot(), f, indent=2)
    return path


def build_graph(findings: List[Dict[str, Any]], controls: List[Dict[str, Any]]):
  g = ExposureGraph()
  g.build(findings, controls)
  g.persist()
  return g

__all__ = ["ExposureGraph", "build_graph", "GRAPH_PATH"]