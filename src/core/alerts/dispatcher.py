"""Alert Dispatcher Abstraction (scaffold).

Supports sending alert payloads to:
- Webhook (HTTP POST JSON)
- Log sink (stdout logger)

Runtime params:
  alerts.enabled (bool)
  alerts.webhook.enabled (bool)
  alerts.webhook.url (str)
  alerts.webhook.timeout_s (float)

Metrics:
  ALERT_DISPATCH_TOTAL (channel, outcome)
"""
from __future__ import annotations
import json, time, logging, urllib.request, urllib.error
from typing import Dict, Any
from config import runtime_params
from core import metrics

log = logging.getLogger("alerts")

class AlertDispatcher:
    def __init__(self):
        self._last_dispatch_ts: float | None = None
        self._dead_letter_path = None
        try:
            import pathlib
            p = pathlib.Path("artifacts/alerts")
            p.mkdir(parents=True, exist_ok=True)
            self._dead_letter_path = p / "dead_letter.jsonl"
        except Exception:
            self._dead_letter_path = None

    def enabled(self) -> bool:
        try:
            v = runtime_params.get_param("alerts.enabled")
            if v in {0, False, "0", "false"}:
                return False
        except Exception:
            pass
        return True

    def dispatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled():
            metrics.ALERT_DISPATCH_TOTAL.labels(channel="disabled", outcome="disabled").inc()
            return {"status": "disabled"}
        self._last_dispatch_ts = time.time()
        results = []
        # Always log sink
        try:
            log.info("ALERT %s", json.dumps(payload)[:500])
            metrics.ALERT_DISPATCH_TOTAL.labels(channel="log", outcome="success").inc()
            results.append({"channel": "log", "status": "ok"})
        except Exception as e:  # noqa: BLE001
            metrics.ALERT_DISPATCH_TOTAL.labels(channel="log", outcome="error").inc()
            results.append({"channel": "log", "status": f"error:{e}"})
        # Webhook sink
        if self._webhook_enabled():
            url = self._webhook_url()
            if url:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                timeout = self._webhook_timeout()
                # basic bounded retries with backoff
                attempts = 0
                last_err = None
                while attempts < 3:
                    attempts += 1
                    try:
                        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
                            status = resp.getcode()
                            if 200 <= status < 300:
                                metrics.ALERT_DISPATCH_TOTAL.labels(channel="webhook", outcome="success").inc()
                                results.append({"channel": "webhook", "status": "ok", "code": status, "attempts": attempts})
                                last_err = None
                                break
                            else:
                                last_err = f"http_{status}"
                    except Exception as e:  # noqa: BLE001
                        last_err = str(e)
                    # backoff sleep (non-blocking stand-in; no async loop here)
                    try:
                        time.sleep(min(0.25 * attempts, 1.0))
                    except Exception:
                        pass
                if last_err is not None:
                    metrics.ALERT_DISPATCH_TOTAL.labels(channel="webhook", outcome="error").inc()
                    results.append({"channel": "webhook", "status": f"error:{last_err}", "attempts": attempts})
                    self._dead_letter({"ts": time.time(), "channel": "webhook", "payload": payload, "error": last_err})
        # return consolidated results
        return {"results": results, "dispatched_at": self._last_dispatch_ts}

    def _dead_letter(self, rec: Dict[str, Any]):
        try:
            if self._dead_letter_path is None:
                return
            with open(self._dead_letter_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, separators=(',',':')) + "\n")
        except Exception:
            pass
        return None

    # --- Webhook helpers ---
    def _webhook_enabled(self) -> bool:
        try:
            v = runtime_params.get_param("alerts.webhook.enabled")
            if v in {1, True, "1", "true"}:
                return True
        except Exception:
            pass
        return False

    def _webhook_url(self) -> str | None:
        try:
            return runtime_params.get_param("alerts.webhook.url")  # type: ignore
        except Exception:
            return None

    def _webhook_timeout(self) -> float:
        try:
            v = runtime_params.get_param("alerts.webhook.timeout_s")
            if v is not None:
                return float(v)
        except Exception:
            pass
        return 3.0

# Singleton
_dispatcher: AlertDispatcher | None = None

def dispatcher() -> AlertDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AlertDispatcher()
    return _dispatcher

__all__ = ["AlertDispatcher", "dispatcher"]
