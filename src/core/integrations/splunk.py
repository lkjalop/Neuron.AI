"""Splunk HEC exporter.

Minimal dependency implementation: uses standard library (urllib) to avoid
introducing requests until needed. If 'requests' library exists it can be
optionally used for simpler code (future optimization).

Runtime Params (expected keys via get_param):
- integration.splunk.enabled (bool, default False)
- integration.splunk.hec_url (str) e.g. https://splunk.example.com:8088/services/collector
- integration.splunk.token (str) HEC auth token
- integration.splunk.source (str, optional) default 'neuron'
- integration.splunk.sourcetype (str, optional) default 'neuron:event'
- integration.splunk.index (str, optional)
- integration.splunk.verify (bool, default True) -- currently ignored (urllib)

Batch Strategy: For now we send each record individually to simplify error attribution.
Future improvement: buffered batch with size/time thresholds.
"""
from __future__ import annotations

from typing import Iterable
import json
import time
import urllib.request
import urllib.error

try:
    from config.runtime_params import get_param  # type: ignore
except Exception:  # pragma: no cover
    def get_param(key: str, default=None):  # type: ignore
        return default
from .base import IExporter, ExportResult, register

DEFAULT_SOURCE = "neuron"
DEFAULT_SOURCETYPE = "neuron:event"

class SplunkHECExporter:
    name = "splunk"

    def enabled(self) -> bool:  # pragma: no cover - trivial
        return bool(get_param("integration.splunk.enabled", False))

    def export(self, records: Iterable[dict]) -> ExportResult:
        records_list = list(records)
        if not self.enabled():
            return {"outcome": "disabled", "count": 0, "latency_s": 0.0}
        if not records_list:
            return {"outcome": "skipped", "count": 0, "latency_s": 0.0}
        url = get_param("integration.splunk.hec_url", None)
        token = get_param("integration.splunk.token", None)
        if not url or not token:
            return {"outcome": "error", "error": "missing_url_or_token", "count": 0, "latency_s": 0.0}
        source = get_param("integration.splunk.source", DEFAULT_SOURCE)
        sourcetype = get_param("integration.splunk.sourcetype", DEFAULT_SOURCETYPE)
        index = get_param("integration.splunk.index", None)
        start = time.perf_counter()
        success = 0
        last_status = None
        for rec in records_list:
            payload = {
                "event": rec,
                "source": source,
                "sourcetype": sourcetype,
            }
            if index:
                payload["index"] = index
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Splunk {token}")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    last_status = resp.getcode()
                    if 200 <= last_status < 300:
                        success += 1
            except urllib.error.HTTPError as e:  # pragma: no cover - network errors
                last_status = e.code
            except Exception:  # pragma: no cover - broad catch, network
                last_status = None
        latency = time.perf_counter() - start
        outcome = "success" if success == len(records_list) else ("partial" if success > 0 else "error")
        return {
            "outcome": outcome,
            "status_code": last_status,
            "latency_s": latency,
            "count": len(records_list),
            "error": None if outcome == "success" else f"success={success}/total={len(records_list)}",
        }

# Register on import
register(SplunkHECExporter())
