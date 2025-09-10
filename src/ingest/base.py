from __future__ import annotations
from typing import Protocol, Iterable, Dict, Any, List, Type
import time

class IngestBatch:
    def __init__(self, source_id: str, items: List[Dict[str, Any]]):
        self.source_id = source_id
        self.items = items
        self.received_ts = time.time()

class Connector(Protocol):
    source_type: str
    def poll(self) -> Iterable[Dict[str, Any]]: ...
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]: ...

class BaseConnector:
    source_type = "generic"
    def __init__(self, source_id: str, config: Dict[str, Any]):
        self.source_id = source_id
        self.config = config
    def poll(self) -> Iterable[Dict[str, Any]]:
        return []
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return raw

_registry: Dict[str, Type[BaseConnector]] = {}

def register_connector(kind: str, cls: Type[BaseConnector]):
    _registry[kind] = cls

def build_connector(kind: str, source_id: str, config: Dict[str, Any]) -> BaseConnector:
    cls = _registry.get(kind)
    if not cls:
        raise ValueError(f"Unknown connector type: {kind}")
    return cls(source_id, config)
