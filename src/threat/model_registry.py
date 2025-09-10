"""Threat Model Registry (skeleton).

Provides minimal in-memory CRUD for threat models to support later
expansion (graph enrichment, ATT&CK coverage, hunting hypotheses).

Data Model (initial):
  id: str
  name: str
  version: int
  description: str
  techniques: list[str]  (MITRE ATT&CK technique IDs)
  assets: list[str]      (related asset IDs)
  created_ts: float
  updated_ts: float

API:
  create_model(payload) -> dict
  get_model(id) -> dict | None
  list_models() -> list[dict]
  update_model(id, patch) -> dict | None
  delete_model(id) -> bool

Future:
  - Persistence layer (Postgres / graph store)
  - Version lineage
  - Risk linkage to findings / components
  - Derived coverage stats (techniques -> control mappings)
"""
from __future__ import annotations

import time, json
from typing import Dict, Any, List, Optional
import uuid
from pathlib import Path

_MODELS: Dict[str, Dict[str, Any]] = {}
_PERSIST_FILE = Path("artifacts/threat_models.json")
_ARTIFACT_VERSION = 1  # increment if on-disk schema changes (backward compatible loader)


def _now() -> float:
    return time.time()


def create_model(data: Dict[str, Any]) -> Dict[str, Any]:
    mid = data.get("id") or str(uuid.uuid4())
    if mid in _MODELS:
        raise ValueError("model_id_exists")
    rec = {
        "id": mid,
        "name": data.get("name") or "unnamed",
        "version": int(data.get("version") or 1),
        "description": data.get("description") or "",
        "techniques": list(data.get("techniques") or []),
        "assets": list(data.get("assets") or []),
        "created_ts": _now(),
        "updated_ts": _now(),
        "metadata": dict(data.get("metadata") or {}),
    }
    _MODELS[mid] = rec
    return rec


def get_model(mid: str) -> Optional[Dict[str, Any]]:
    return _MODELS.get(mid)


def list_models(limit: int = 100) -> List[Dict[str, Any]]:
    return list(_MODELS.values())[:limit]


def update_model(mid: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rec = _MODELS.get(mid)
    if not rec:
        return None
    for k in ["name", "description"]:
        if k in patch:
            rec[k] = patch[k]
    if "techniques" in patch:
        rec["techniques"] = list(patch["techniques"])  # type: ignore
    if "assets" in patch:
        rec["assets"] = list(patch["assets"])  # type: ignore
    if "metadata" in patch and isinstance(patch["metadata"], dict):
        rec["metadata"].update(patch["metadata"])  # type: ignore
    rec["version"] = int(patch.get("version", rec["version"]))
    rec["updated_ts"] = _now()
    return rec


def delete_model(mid: str) -> bool:
    return _MODELS.pop(mid, None) is not None


def save() -> int:
    """Persist threat models to disk including artifact version wrapper.

    Format (v1): {"version": 1, "models": [ ...model dicts... ]}
    Legacy (v0) plain list is still accepted on load.
    """
    try:
        _PERSIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": _ARTIFACT_VERSION, "models": list(_MODELS.values())}
        _PERSIST_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return len(_MODELS)
    except Exception:
        return 0


def load() -> int:
    if not _PERSIST_FILE.exists():
        return 0
    try:
        raw = _PERSIST_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        models: list[dict] = []
        if isinstance(data, dict) and "models" in data:
            # v1+ format
            models = data.get("models") or []
        elif isinstance(data, list):  # legacy v0
            models = data
        if isinstance(models, list):
            _MODELS.clear()
            for rec in models:
                if isinstance(rec, dict) and rec.get("id"):
                    _MODELS[rec["id"]] = rec
            return len(_MODELS)
    except Exception:
        return 0
    return 0


__all__ = [
    "create_model",
    "get_model",
    "list_models",
    "update_model",
    "delete_model",
    "save",
    "load",
    "_ARTIFACT_VERSION",
]