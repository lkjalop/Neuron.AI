from __future__ import annotations
"""External vulnerability intelligence feed fetchers (placeholders).

Provides lightweight async HTTP fetch helpers for:
 - NVD (CVE JSON 2.0) recent modified
 - OSV (batch query or single ID)
 - EPSS (Exploit Prediction Scoring System) daily probabilities
 - KEV (Known Exploited Vulnerabilities) catalog

Design Goals:
 - Central retry & timeout policy
 - Normalized return structures consumed by normalizers/enricher
 - Best-effort: failures return empty lists so scanner loop degrades gracefully

Environment / Runtime Params (future expansion):
 - vuln.feed.nvd.enabled (default 1)
 - vuln.feed.osv.enabled (default 1)
 - vuln.feed.epss.enabled (default 1)
 - vuln.feed.kev.enabled (default 1)
 - vuln.feed.http_timeout_s (default 8)
 - vuln.feed.max_items (cap list size; default 500)
"""

import asyncio, json, time, csv, io, math, random
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta

try:
    import aiohttp  # type: ignore
except Exception:  # noqa: BLE001
    aiohttp = None  # type: ignore

from config.runtime_params import get_param
from core import metrics
try:
    from storage import vuln_store  # type: ignore
except Exception:  # noqa: BLE001
    vuln_store = None  # type: ignore

USER_AGENT = "NeuronVulnScanner/0.1"

_RATE_STATE: Dict[str, float] = {}
_BACKOFF_STATE: Dict[str, float] = {}


async def _http_get(url: str, timeout: float, etag: str | None = None, if_modified_since: str | None = None) -> Tuple[Any, Optional[str], int]:
    if not aiohttp:
        return None, None, 0
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as sess:
            headers = {}
            if etag:
                headers["If-None-Match"] = etag
            if if_modified_since:
                headers["If-Modified-Since"] = if_modified_since
            start = time.time()
            async with sess.get(url, timeout=timeout, headers=headers) as resp:
                status = resp.status
                new_etag = resp.headers.get("ETag")
                latency = time.time() - start
                metrics.VULN_FEED_FETCH_LATENCY.labels(feed=url.split('/')[2][:40]).observe(latency)
                if status == 304:
                    metrics.VULN_FEED_FETCH_STATUS.labels(feed=url.split('/')[2][:40], status="not_modified").inc()
                    return None, new_etag, status
                if status != 200:
                    metrics.VULN_FEED_FETCH_STATUS.labels(feed=url.split('/')[2][:40], status=str(status)).inc()
                    return None, new_etag, status
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype:
                    data = await resp.json()
                else:
                    data = await resp.text()
                metrics.VULN_FEED_FETCH_STATUS.labels(feed=url.split('/')[2][:40], status="200").inc()
                return data, new_etag, status
    except Exception:
        metrics.VULN_FEED_FETCH_STATUS.labels(feed=url.split('/')[2][:40], status="error").inc()
        return None, None, 0


def _rate_limit(feed: str):
    min_interval = float(get_param(f"vuln.feed.{feed}.min_interval_s", 5.0))
    last = _RATE_STATE.get(feed, 0.0)
    now = time.time()
    if now - last < min_interval:
        raise RuntimeError("rate_limited")
    _RATE_STATE[feed] = now

def _apply_backoff(feed: str, success: bool):
    if success:
        _BACKOFF_STATE[feed] = 0.0
        metrics.VULN_FEED_BACKOFF_SECONDS.labels(feed=feed).set(0.0)
        return
    current = _BACKOFF_STATE.get(feed, 0.0) or 1.0
    # exponential up to max
    max_backoff = float(get_param(f"vuln.feed.{feed}.max_backoff_s", 300.0))
    new_backoff = min(max_backoff, current * 2.0 if current > 0 else 1.0)
    # jitter 0.8 - 1.2x
    jitter = random.uniform(0.8, 1.2)
    new_backoff *= jitter
    _BACKOFF_STATE[feed] = new_backoff
    metrics.VULN_FEED_BACKOFF_SECONDS.labels(feed=feed).set(new_backoff)

async def fetch_nvd_recent(since_hours: int = 24) -> List[Dict[str, Any]]:
    if int(get_param("vuln.feed.nvd.enabled", 1)) == 0:
        return []
    # NVD API rate limits; for placeholder, we call 1.0 modified feed subset (mock endpoint or skip if offline)
    # Official NVD API requires key for higher rate; here we skip real call if offline.
    # Provide synthetic structure similar to normalizer expectation.
    # Future: implement pagination & API key usage when provided.
    # If network disabled (aiohttp None) produce deterministic sample.
    if not aiohttp:
        now = datetime.now(timezone.utc).isoformat()
        return [{"cve": {"id": "CVE-2025-1000"}, "metrics": {}, "published": now}]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    params_base = f"lastModStartDate={cutoff.isoformat()}"
    timeout = float(get_param("vuln.feed.http_timeout_s", 8.0))
    etag = None
    if_modified_since = None
    # Retrieve prior ETag from feed_state (best-effort)
    if vuln_store:
        try:
            state = await vuln_store.get_feed_state("nvd")  # type: ignore[attr-defined]
            if state:
                if state.get("etag"):
                    etag = state.get("etag")
                # use last_fetch_ts for If-Modified-Since (approx) if available
                lfts = state.get("last_fetch_ts")
                if lfts:
                    if_modified_since = datetime.utcfromtimestamp(float(lfts)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        except Exception:
            etag = None
    try:
        _rate_limit("nvd")
    except RuntimeError:
        return []
    collected: List[Dict[str, Any]] = []
    start_index = 0
    page_size = int(get_param("vuln.feed.nvd.page_size", 200))
    max_items = int(get_param("vuln.feed.max_items", 500))
    failure = False
    while len(collected) < max_items:
        url = f"{base_url}?{params_base}&resultsPerPage={page_size}&startIndex={start_index}"
        data, new_etag, status = await _http_get(url, timeout, etag if start_index == 0 else None, if_modified_since if start_index == 0 else None)
        if status == 304:
            break
        if not data or status != 200:
            failure = True
            break
        items = (data.get("vulnerabilities", []) if isinstance(data, dict) else [])
        if not items:
            break
        for item in items:
            if len(collected) >= max_items:
                break
            try:
                cve_obj = item.get("cve") or {}
                published = cve_obj.get("published") or datetime.now(timezone.utc).isoformat()
                collected.append({"cve": {"id": cve_obj.get("id")}, "metrics": cve_obj.get("metrics", {}), "published": published})
            except Exception:
                continue
        # NVD includes totalResults maybe; attempt pagination heuristic
        total_results = data.get("totalResults") if isinstance(data, dict) else None
        start_index += page_size
        if total_results is not None and start_index >= total_results:
            break
    # Update feed state
    if vuln_store:
        try:
            status_flag = "ok" if not failure else "error"
            await vuln_store.upsert_feed_state("nvd", new_etag if not failure else etag, status_flag, None if not failure else "fetch_error")  # type: ignore[attr-defined]
        except Exception:
            pass
    _apply_backoff("nvd", success=not failure)
    # Freshness age metric
    if vuln_store and collected:
        try:
            metrics.VULN_FEED_FRESHNESS_AGE_SECONDS.labels(feed="nvd").set(0.0)
        except Exception:
            pass
    return collected

async def fetch_osv_recent(since_hours: int = 24) -> List[Dict[str, Any]]:
    if int(get_param("vuln.feed.osv.enabled", 1)) == 0:
        return []
    # Placeholder: OSV bulk query requires listing ecosystems / packages; we produce synthetic sample if offline.
    if not aiohttp:
        return [{"id": "OSV-2025-DEMO", "aliases": ["CVE-2025-2000"]}]
    try:
        _rate_limit("osv")
    except RuntimeError:
        return []
    # OSV doesn't have a pure "recent all" unauth endpoint; keep placeholder empty to avoid huge pulls.
    return []

async def fetch_epss(cve_ids: List[str]) -> Dict[str, float]:
    if int(get_param("vuln.feed.epss.enabled", 1)) == 0:
        return {}
    if not cve_ids:
        return {}
    # EPSS daily CSV (fallback deterministic if no network)
    if not aiohttp:
        scores: Dict[str, float] = {}
        for c in cve_ids:
            try:
                h = int(c[-1], 16)
                scores[c] = round(h / 15.0, 4)
            except Exception:
                scores[c] = 0.05
        return scores
    timeout = float(get_param("vuln.feed.http_timeout_s", 8.0))
    url = "https://epss.cyentia.com/epss_scores.csv"  # example; not the official, placeholder
    try:
        _rate_limit("epss")
    except RuntimeError:
        return {}
    data, _etag, status = await _http_get(url, timeout)
    if status != 200 or not data:
        return {}
    scores: Dict[str, float] = {}
    try:
        reader = csv.reader(io.StringIO(data))
        for row in reader:
            # Expect: CVE,EPS,Percentile; skip header
            if not row or row[0].startswith("CVE") and row[0] != "CVE":
                pass
            if len(row) >= 2 and row[0] in cve_ids:
                try:
                    scores[row[0]] = round(float(row[1]), 4)
                except Exception:
                    continue
    except Exception:
        return {}
    return scores

async def fetch_kev_catalog() -> set[str]:
    if int(get_param("vuln.feed.kev.enabled", 1)) == 0:
        return set()
    if not aiohttp:
        return {"CVE-2025-1000"}
    timeout = float(get_param("vuln.feed.http_timeout_s", 8.0))
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    try:
        _rate_limit("kev")
    except RuntimeError:
        return set()
    data, _etag, status = await _http_get(url, timeout)
    if status != 200 or not data:
        return set()
    out: set[str] = set()
    try:
        vulns = data.get("vulnerabilities", []) if isinstance(data, dict) else []
        for v in vulns:
            cve = v.get("cveID")
            if cve:
                out.add(cve)
    except Exception:
        return set()
    return out

async def gather_all_sources() -> List[Dict[str, Any]]:
    # Parallel fetch recent items
    tasks = [
        fetch_nvd_recent(),
        fetch_osv_recent(),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    docs: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            docs.extend(r)
    return docs

__all__ = [
    "fetch_nvd_recent",
    "fetch_osv_recent",
    "fetch_epss",
    "fetch_kev_catalog",
    "gather_all_sources",
]
