"""Integration exporter base interfaces and registry.

Lightweight pluggable system for pushing anomalies / governance events
into external systems (SIEM, ITSM, EDR, Threat Intel, etc.).

Design goals:
- Minimal dependency surface (standard library only here)
- Exporters handle their own enable/disable logic via runtime params
- Central registry dispatch; safe failure isolation per exporter
- Metrics + audit hooks (increment / latency added by caller)
"""
from __future__ import annotations

from typing import Protocol, TypedDict, Callable, Iterable, List, Dict, Any, Optional
import time
import traceback

class ExportResult(TypedDict, total=False):
    outcome: str  # success|error|skipped|disabled|noop
    status_code: int | None
    latency_s: float
    error: str | None
    count: int  # number of records exported (0 if none)

class IExporter(Protocol):
    name: str

    def enabled(self) -> bool:
        """Return True if exporter should run (runtime param driven)."""
        ...

    def export(self, records: Iterable[dict]) -> ExportResult:
        """Export a batch of anomaly-like records.

        Implementations should:
        - Return outcome 'disabled' if not enabled
        - Return outcome 'skipped' if records empty
        - Catch internal transient errors and surface outcome 'error'
        - Populate latency_s and count
        """
        ...

_registry: Dict[str, IExporter] = {}

def register(exporter: IExporter) -> None:
    _registry[exporter.name] = exporter

def get(name: str) -> Optional[IExporter]:
    return _registry.get(name)

def list_exporters() -> List[str]:
    return list(_registry.keys())

def active_exporters() -> List[IExporter]:
    return [e for e in _registry.values() if _safe_enabled(e)]

def _safe_enabled(exp: IExporter) -> bool:
    try:
        return exp.enabled()
    except Exception:
        return False

def export_all(records: List[dict], audit_callback: Optional[Callable[[str, ExportResult], None]] = None,
               metrics_callback: Optional[Callable[[str, ExportResult], None]] = None) -> List[tuple[str, ExportResult]]:
    """Dispatch a batch of records to all registered exporters.

    Each exporter is isolated; failures are contained and reported in outcome.
    audit_callback(name, result) if provided will be called after each attempt.
    metrics_callback(name, result) likewise.
    """
    results: List[tuple[str, ExportResult]] = []
    for name, exporter in _registry.items():
        start = time.perf_counter()
        try:
            if not _safe_enabled(exporter):
                res: ExportResult = {"outcome": "disabled", "status_code": None, "latency_s": 0.0, "error": None, "count": 0}
            else:
                res = exporter.export(records)
                # Ensure minimum fields
                res.setdefault("latency_s", time.perf_counter() - start)
                res.setdefault("count", len(records))
                if "outcome" not in res:
                    res["outcome"] = "success"
        except Exception as e:  # broad safeguard
            res = {
                "outcome": "error",
                "status_code": None,
                "latency_s": time.perf_counter() - start,
                "error": f"{e.__class__.__name__}: {e}",
                "count": len(records),
            }
        if metrics_callback:
            try:
                metrics_callback(name, res)
            except Exception:
                pass
        if audit_callback:
            try:
                audit_callback(name, res)
            except Exception:
                pass
        results.append((name, res))
    return results
