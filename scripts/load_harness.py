"""Load harness to exercise ingestion endpoint and record performance metrics.

Outputs JSON artifact at `artifacts/perf/load_metrics.json` capturing:
    - total_events, duration_seconds, events_per_second
    - latency_ms: p50, p90, p95, p99, max, average
    - error_count

Two modes:
    1. External HTTP (default): requires a running server at --url.
    2. In-process (`--inprocess`): spins up the FastAPI app inside the harness using
         an ASGI-aware HTTPX client (no separate server needed) and runs startup/shutdown
         events automatically. This avoids needing a second terminal in constrained
         environments and ensures /ingest + pipeline are active.

Usage:
    External:
        python scripts/load_harness.py --url http://localhost:8000/ingest --tenants tenantA tenantB \
                --events 1000 --concurrency 10
    In-process:
        python scripts/load_harness.py --inprocess --events 1000 --concurrency 10 --tenants tenantA tenantB
"""
from __future__ import annotations

import argparse, asyncio, time, json, statistics, os, sys, pathlib

# Auto-add src directory to sys.path for in-process usage without requiring PYTHONPATH env.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from pathlib import Path
from typing import List

try:  # External HTTP client
    import aiohttp  # type: ignore
except ImportError:  # pragma: no cover - optional if using --inprocess only
    aiohttp = None  # type: ignore

try:  # In-process HTTP client
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


def percentiles(samples: List[float], points=(50, 90, 95, 99)):
    if not samples:
        return {f"p{p}": None for p in points}
    s = sorted(samples)
    n = len(s)
    out = {}
    for p in points:
        k = (p/100)*(n-1)
        f = int(k)
        c = min(f+1, n-1)
        if f == c:
            out[f"p{p}"] = s[f]
        else:
            d = k - f
            out[f"p{p}"] = s[f] + (s[c]-s[f])*d
    return out

async def worker_external(session, url: str, tenant: str, count: int, payload_template: dict, latency_sink: List[float], error_counter: List[int]):
    for _ in range(count):
        payload = dict(payload_template)
        payload["tenant_id"] = tenant
        t0 = time.perf_counter()
        try:  # noqa: PERF203 (small loop ok)
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    error_counter[0] += 1
                else:
                    await resp.read()
        except Exception:
            error_counter[0] += 1
        latency_sink.append((time.perf_counter() - t0) * 1000)


async def worker_inprocess(client, tenant: str, count: int, payload_template: dict, latency_sink: List[float], error_counter: List[int]):
    for _ in range(count):
        payload = dict(payload_template)
        payload["tenant_id"] = tenant
        t0 = time.perf_counter()
        try:
            resp = await client.post("/ingest", json=payload)
            if resp.status_code >= 400:
                error_counter[0] += 1
        except Exception:
            error_counter[0] += 1
        latency_sink.append((time.perf_counter() - t0) * 1000)

async def run_load_external(url: str, tenants: List[str], events: int, concurrency: int, payload_template: dict):
    if aiohttp is None:
        raise RuntimeError("aiohttp not installed; install or use --inprocess mode")
    per_worker = max(1, events // concurrency)
    latency: List[float] = []
    errors = [0]
    start = time.perf_counter()
    connector = aiohttp.TCPConnector(limit=concurrency * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for i in range(concurrency):
            tenant = tenants[i % len(tenants)]
            tasks.append(asyncio.create_task(worker_external(session, url, tenant, per_worker, payload_template, latency, errors)))
        await asyncio.gather(*tasks)
    duration = time.perf_counter() - start
    return latency, errors[0], duration, per_worker * concurrency


async def run_load_inprocess(tenants: List[str], events: int, concurrency: int, payload_template: dict):
    if httpx is None:
        raise RuntimeError("httpx not installed; add to requirements or run pip install httpx")
    # Import app lazily so requirements for external mode remain minimal.
    from core.main import app  # noqa: WPS433
    per_worker = max(1, events // concurrency)
    latency: List[float] = []
    errors = [0]
    start = time.perf_counter()
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:  # type: ignore[arg-type]
        tasks = []
        for i in range(concurrency):
            tenant = tenants[i % len(tenants)]
            tasks.append(asyncio.create_task(worker_inprocess(client, tenant, per_worker, payload_template, latency, errors)))
        await asyncio.gather(*tasks)
        # Allow a brief window for pipeline async processing to drain
        await asyncio.sleep(0.2)
    duration = time.perf_counter() - start
    return latency, errors[0], duration, per_worker * concurrency


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/ingest")
    ap.add_argument("--tenants", nargs="*", default=["tenantA"]) 
    ap.add_argument("--events", type=int, default=500)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--burst", type=int, default=0, help="Reserved for future burst mode")
    ap.add_argument("--out", default="artifacts/perf/load_metrics.json")
    ap.add_argument("--inprocess", action="store_true", help="Run against in-process app (no external server needed)")
    ap.add_argument("--inject-anomalies", action="store_true", help="Inject synthetic anomalies after warm-up phase")
    ap.add_argument("--warmup-events", type=int, default=50, help="Events per tenant treated as warm-up before anomaly injection")
    ap.add_argument("--anomaly-factor", type=float, default=4.0, help="Multiplier applied to feature value to create anomalies")
    args = ap.parse_args()
    os.makedirs(Path(args.out).parent, exist_ok=True)
    payload_template = {"source": "load", "raw": {}, "features": {"cpu": 0.9}}
    if args.inprocess:
        latency, errors, duration, sent = asyncio.run(run_load_inprocess(args.tenants, args.events, args.concurrency, payload_template))
    else:
        latency, errors, duration, sent = asyncio.run(run_load_external(args.url, args.tenants, args.events, args.concurrency, payload_template))

    # Optional anomaly injection pass (simple replay with amplified values)
    injected = 0
    if args.inject_anomalies:
        try:
            import httpx  # type: ignore
            from core.main import app  # type: ignore
            async def inject():
                async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:  # type: ignore[arg-type]
                    import random
                    for tenant in args.tenants:
                        # Warm-up with slight jitter to establish non-zero variance
                        for _ in range(20):
                            base_cpu = 1.0 + random.uniform(-0.03, 0.03)
                            base_mem = 1.0 + random.uniform(-0.03, 0.03)
                            payload = {"tenant_id": tenant, "source": "warmup", "features": {"cpu": base_cpu, "mem": base_mem}}
                            await client.post("/ingest", json=payload, headers={"x-inline-detect": "true"})
                        # Inject escalating anomalies
                        spikes = []
                        for i in range(6):
                            val = args.anomaly_factor * (1 + i * 0.2)
                            spikes.append({"cpu": val, "mem": val * 0.8})
                        for featset in spikes:
                            payload = {"tenant_id": tenant, "source": "inject", "features": featset}
                            await client.post("/ingest", json=payload, headers={"x-inline-detect": "true"})
                    # Allow detector pipeline time to drain queue for injected anomalies
                    await asyncio.sleep(0.5)
            if args.inprocess:
                asyncio.run(inject())
                injected = len(args.tenants) * 6
        except Exception:  # pragma: no cover
            pass
    pct = percentiles(latency)
    avg = statistics.mean(latency) if latency else None
    artifact = {
        "total_events": sent,
        "duration_seconds": duration,
        "events_per_second": sent / duration if duration else None,
        "latency_ms": {
            "average": avg,
            "max": max(latency) if latency else None,
            **pct,
        },
        "error_count": errors,
        "tenants": args.tenants,
        "concurrency": args.concurrency,
    "url": args.url,
    "anomalies_injected": injected,
    "anomaly_factor": args.anomaly_factor if args.inject_anomalies else None,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(json.dumps(artifact, indent=2))

if __name__ == "__main__":  # pragma: no cover
    main()
