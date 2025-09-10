"""Threat Feed Manager (scaffold).

Design Goals:
- Pluggable feed sources (URL, local file, API)
- Backoff with jitter & max cap
- Runtime param gating: threat.feeds.enabled, threat.feed.<name>.enabled
- Metrics integration (THREAT_FEED_* metrics)
- Lightweight in-memory store of indicators per feed

Indicator Model (simplified): {"value": str, "type": str, "tags": list[str], "first_seen": float, "last_seen": float}

Future Enhancements:
- Persistence to sqlite/postgres
- TTL pruning & scoring
- Confidence weighting
"""
from __future__ import annotations
import time, random, threading
from typing import Dict, List, Callable, Optional
from config import runtime_params
from core import metrics
import json, urllib.request, urllib.error

class ThreatFeed:
    def __init__(self, name: str, fetch_fn: Callable[[], List[dict]], interval_s: float = 300.0):
        self.name = name
        self.fetch_fn = fetch_fn
        self.interval_s = interval_s
        self._last_success: float | None = None
        self._last_attempt: float | None = None
        self._backoff: float = 0.0
        self._indicators: Dict[str, dict] = {}  # key by value
        self._lock = threading.Lock()
        self._force_error = False  # test hook

    def indicators(self) -> List[dict]:
        with self._lock:
            return list(self._indicators.values())

    def age_seconds(self) -> float:
        if self._last_success is None:
            return 1e9
        return time.time() - self._last_success

    def due(self) -> bool:
        if self._last_attempt is None:
            return True
        return (time.time() - self._last_attempt) >= max(self.interval_s, self._backoff)

    def fetch_once(self) -> None:
        # Gating
        if not self._enabled():
            metrics.THREAT_FEED_STATUS_TOTAL.labels(feed=self.name, status="disabled").inc()
            return
        if not self.due():
            return
        self._last_attempt = time.time()
        try:
            if self._force_error:
                raise RuntimeError("forced_error")
            start = time.time()
            rows = self.fetch_fn() or []
            metrics.THREAT_FEED_FETCH_LATENCY.labels(feed=self.name).observe(time.time() - start)
            added = 0
            updated = 0
            now = time.time()
            with self._lock:
                for row in rows:
                    val = str(row.get("value") or "").strip()
                    if not val:
                        continue
                    rec = self._indicators.get(val)
                    if rec:
                        rec["last_seen"] = now
                        updated += 1
                    else:
                        self._indicators[val] = {
                            "value": val,
                            "type": row.get("type") or "generic",
                            "tags": row.get("tags") or [],
                            "first_seen": now,
                            "last_seen": now,
                        }
                        added += 1
            self._last_success = time.time()
            self._backoff = 0.0
            metrics.THREAT_FEED_STATUS_TOTAL.labels(feed=self.name, status="success").inc()
            metrics.THREAT_FEED_AGE_SECONDS.labels(feed=self.name).set(0.0)
        except Exception:
            # Exponential backoff with jitter
            self._backoff = min(max(2.0, self._backoff * 2 or 2.0) * random.uniform(0.9,1.1), 3600.0)
            metrics.THREAT_FEED_STATUS_TOTAL.labels(feed=self.name, status="error").inc()
            metrics.THREAT_FEED_BACKOFF_SECONDS.labels(feed=self.name).set(self._backoff)
        else:
            metrics.THREAT_FEED_BACKOFF_SECONDS.labels(feed=self.name).set(self._backoff)

    def _enabled(self) -> bool:
        try:
            if runtime_params:
                global_flag = runtime_params.get_param("threat.feeds.enabled")
                if global_flag in {0, False, "0", "false"}:
                    return False
                feed_flag = runtime_params.get_param(f"threat.feed.{self.name}.enabled")
                if feed_flag in {0, False, "0", "false"}:
                    return False
        except Exception:
            pass
        return True

class ThreatFeedManager:
    def __init__(self):
        self._feeds: Dict[str, ThreatFeed] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def register(self, feed: ThreatFeed):
        self._feeds[feed.name] = feed

    def get(self, name: str) -> ThreatFeed | None:
        return self._feeds.get(name)

    def list(self) -> List[str]:
        return list(self._feeds.keys())

    def indicators(self, feed: str | None = None) -> List[dict]:
        if feed:
            f = self._feeds.get(feed)
            if not f:
                return []
            return f.indicators()
        out: List[dict] = []
        for f in self._feeds.values():
            out.extend(f.indicators())
        return out

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="threat-feed-loop", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            for feed in list(self._feeds.values()):
                try:
                    feed.fetch_once()
                    if feed._last_success:
                        metrics.THREAT_FEED_AGE_SECONDS.labels(feed=feed.name).set(feed.age_seconds())
                except Exception:
                    pass
            self._stop.wait(5.0)

threat_feed_manager = ThreatFeedManager()

# Default demo feed (static list function) - placeholder

def _demo_feed_fetch():
    return [
        {"value": "mal.domain.example", "type": "domain", "tags": ["demo"]},
        {"value": "203.0.113.44", "type": "ip", "tags": ["demo"]},
    ]

# Register demo feed (can be disabled via runtime params)
threat_feed_manager.register(ThreatFeed("demo", _demo_feed_fetch, interval_s=60.0))

# URL-based feed example with in-memory cache and basic JSON mapping
_url_cache: dict[str, tuple[float, list[dict]]] = {}

def _url_feed_fetch(url: str, value_key: str = "value", type_key: str = "type", tags_key: str = "tags", ttl_s: float = 120.0):
    now = time.time()
    cached = _url_cache.get(url)
    if cached and (now - cached[0]) < ttl_s:
        return cached[1]
    try:
        req = urllib.request.Request(url, headers={"Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:  # nosec B310 demo
            data = json.loads(resp.read().decode("utf-8"))
            rows = []
            if isinstance(data, list):
                for it in data:
                    if not isinstance(it, dict):
                        continue
                    rows.append({
                        "value": str(it.get(value_key, "")),
                        "type": str(it.get(type_key, "generic")),
                        "tags": list(it.get(tags_key, []) or []),
                    })
            _url_cache[url] = (now, rows)
            return rows
    except Exception:
        return []

# Register a sample URL feed (points to a placeholder path; user can override via params later)
def _url_sample_fetch():
    try:
        url = runtime_params.get_param("threat.feed.url_sample.url") or "http://127.0.0.1:8000/threat-feeds/sample.json"
        vkey = runtime_params.get_param("threat.feed.url_sample.keys.value") or "value"
        tkey = runtime_params.get_param("threat.feed.url_sample.keys.type") or "type"
        gkey = runtime_params.get_param("threat.feed.url_sample.keys.tags") or "tags"
        ttl = float(runtime_params.get_param("threat.feed.url_sample.ttl_s") or 120.0)
    except Exception:
        url, vkey, tkey, gkey, ttl = "http://127.0.0.1:8000/threat-feeds/sample.json", "value", "type", "tags", 120.0
    return _url_feed_fetch(url, value_key=vkey, type_key=tkey, tags_key=gkey, ttl_s=ttl)

threat_feed_manager.register(ThreatFeed("url_sample", _url_sample_fetch, interval_s=90.0))
