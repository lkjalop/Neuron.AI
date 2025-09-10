from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, List
from ..model.finding import Finding

class ScanContext:
    def __init__(self, params: Dict[str, Any], ontology_store: Dict[str, Any] | None = None):
        self.params = params
        self.ontology_store = ontology_store or {}

class ScannerPlugin(ABC):
    key: str = "base"
    description: str = "Abstract base plugin"

    @abstractmethod
    def scan(self, items: Iterable[Dict[str, Any]], ctx: ScanContext) -> List[Finding]:
        """Produce findings from input iterable of items (events, resources, etc.)."""
        raise NotImplementedError
