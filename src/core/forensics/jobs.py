"""Forensics job scaffold (Phase 6 / 7 bridge).

Provides lightweight in-memory job registry + submission helpers.
A later worker (Todo 22) will consume queued jobs and populate results.
For the 'memory' modality we optionally delegate to existing forensics.memory.submit_memory_job
for immediate execution so tests can observe completed jobs early.
"""
from __future__ import annotations
import time, uuid, threading
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from core import metrics
import os, json, pathlib

_ALLOWED_MODALITIES = {"memory", "disk", "network"}

@dataclass
class ForensicsJob:
    id: str
    modality: str
    submitted_ts: float
    status: str  # submitted|queued|running|done|error
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_record(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

_jobs: Dict[str, ForensicsJob] = {}
_jobs_order: List[str] = []  # preserve insertion for listing
_lock = threading.Lock()
_WORKER_TASK = None  # set by main app on startup (optional)
_WORKER_SEMAPHORE = None  # lazily created asyncio.Semaphore
_MAX_CONCURRENT = int(os.getenv("FORENSICS_MAX_CONCURRENT", "2"))
_JOB_MAX_RUNTIME = float(os.getenv("FORENSICS_JOB_MAX_RUNTIME", "5"))  # seconds
_JOB_MAX_RETRIES = int(os.getenv("FORENSICS_JOB_MAX_RETRIES", "3"))
_PERSIST_PATH = pathlib.Path("artifacts/forensics/jobs.jsonl")
_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
_MAX_BYTES = 5_000_000
_MAX_LINES = 20000

def _rotate_if_needed():  # best-effort
    try:
        if not _PERSIST_PATH.exists():
            return
        st = _PERSIST_PATH.stat()
        if st.st_size < _MAX_BYTES:
            # quick line sampling
            line_count = 0
            with _PERSIST_PATH.open('r', encoding='utf-8') as f:
                for line_count, _ in enumerate(f, start=1):
                    if line_count >= _MAX_LINES:
                        break
            if line_count < _MAX_LINES and st.st_size < _MAX_BYTES:
                return
        # rotate chain .1 .2 .3 (keep 3)
        for idx in range(3,0,-1):
            p = _PERSIST_PATH.parent / f"jobs.jsonl.{idx}"
            if idx == 3 and p.exists():
                try: p.unlink()
                except Exception: pass
        for idx in range(2,0,-1):
            src = _PERSIST_PATH.parent / f"jobs.jsonl.{idx}"
            dst = _PERSIST_PATH.parent / f"jobs.jsonl.{idx+1}"
            if src.exists():
                try: os.replace(src, dst)
                except Exception: pass
        try: os.replace(_PERSIST_PATH, _PERSIST_PATH.parent / "jobs.jsonl.1")
        except Exception: pass
    except Exception:
        pass

def _persist(job: ForensicsJob):  # append JSON line
    try:
        _rotate_if_needed()
        with _PERSIST_PATH.open('a', encoding='utf-8') as f:
            f.write(json.dumps(job.to_record(), separators=(',',':')) + '\n')
    except Exception:
        try:
            metrics.FORENSICS_JOB_PERSIST_ERRORS_TOTAL.labels(stage="append").inc()  # type: ignore[attr-defined]
        except Exception:
            pass
        pass

def _load_existing(limit: int = 5000):
    if not _PERSIST_PATH.exists():
        return
    try:
        with _PERSIST_PATH.open('r', encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                try:
                    job = ForensicsJob(**rec)
                except Exception:
                    continue
                _jobs[job.id] = job
                _jobs_order.append(job.id)
                if len(_jobs_order) >= limit:
                    break
    except Exception:
        try:
            metrics.FORENSICS_JOB_PERSIST_ERRORS_TOTAL.labels(stage="load").inc()  # type: ignore[attr-defined]
        except Exception:
            pass
        pass

_load_existing()

def _next_queued_job() -> ForensicsJob | None:
    for jid in list(_jobs_order):
        job = _jobs.get(jid)
        if job and job.status == "queued":
            return job
    return None

async def _worker_loop():  # pragma: no cover (timing/async)
    import asyncio
    global _WORKER_SEMAPHORE
    if _WORKER_SEMAPHORE is None:
        _WORKER_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT)
    while True:
        try:
            job = _next_queued_job()
            if not job:
                await asyncio.sleep(1.0)
                continue
            async with _WORKER_SEMAPHORE:
                job.status = "running"
                attempt = 0
                start_ts = time.time()
                while attempt <= _JOB_MAX_RETRIES:
                    attempt += 1
                    try:
                        # Timeout guard per attempt
                        async def _do_acquire():
                            # Simulate acquisition latency
                            await asyncio.sleep(0.05)
                            # Produce dummy result based on modality; random failure injection
                            if job.modality == "disk":
                                return {"files_scanned": 120, "suspicious": 1}
                            elif job.modality == "network":
                                return {"flows": 45, "anomalous_flows": 2}
                            else:
                                return {"info": "generic_job_completed"}
                        result = await asyncio.wait_for(_do_acquire(), timeout=_JOB_MAX_RUNTIME)
                        job.result = result
                        job.status = "done"
                        try:
                            metrics.FORENSICS_JOB_TOTAL.labels(modality=job.modality, status="done").inc()  # type: ignore[attr-defined]
                            metrics.FORENSICS_FINDINGS_TOTAL.labels(modality=job.modality).inc()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        break
                    except asyncio.TimeoutError:
                        job.error = "timeout"
                        if attempt <= _JOB_MAX_RETRIES:
                            try: metrics.FORENSICS_JOB_RETRIES_TOTAL.labels(modality=job.modality, outcome="retry").inc()  # type: ignore[attr-defined]
                            except Exception: pass
                            await asyncio.sleep(min(0.2 * attempt, 1.0))
                            continue
                    except Exception as e:  # noqa: BLE001
                        job.error = str(e)
                        if attempt <= _JOB_MAX_RETRIES:
                            try: metrics.FORENSICS_JOB_RETRIES_TOTAL.labels(modality=job.modality, outcome="retry").inc()  # type: ignore[attr-defined]
                            except Exception: pass
                            await asyncio.sleep(min(0.2 * attempt, 1.0))
                            continue
                if job.status != "done":
                    job.status = "error"
                    try: metrics.FORENSICS_JOB_TOTAL.labels(modality=job.modality, status="error").inc()  # type: ignore[attr-defined]
                    except Exception: pass
                    try: metrics.FORENSICS_JOB_RETRIES_TOTAL.labels(modality=job.modality, outcome="exhausted").inc()  # type: ignore[attr-defined]
                    except Exception: pass
                try:
                    _persist(job)
                except Exception:
                    pass
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.5)

async def submit_job(modality: str, params: Dict[str, Any] | None = None) -> ForensicsJob:
    modality = modality.lower()
    if modality not in _ALLOWED_MODALITIES:
        raise ValueError("unsupported_modality")
    params = params or {}
    # Fast path for memory modality: leverage existing async acquisition scaffold
    if modality == "memory":
        try:
            from forensics.memory import submit_memory_job  # type: ignore
            rec = await submit_memory_job(params.get("asset_id") or "unknown", params)
            # Wrap into ForensicsJob
            job = ForensicsJob(
                id=rec.get("id"),  # type: ignore[arg-type]
                modality=modality,
                submitted_ts=rec.get("submitted", time.time()),
                status=rec.get("status", "done"),
                params=params,
                result={k: v for k, v in rec.items() if k not in {"id", "status", "submitted", "modality"}},
            )
            with _lock:
                _jobs[job.id] = job
                _jobs_order.append(job.id)
            _persist(job)
            return job
        except Exception:  # fall back to queued semantics
            pass
    job = ForensicsJob(
        id=uuid.uuid4().hex[:16],
        modality=modality,
        submitted_ts=time.time(),
        status="queued",
        params=params,
    )
    try:
        metrics.FORENSICS_JOB_TOTAL.labels(modality=modality, status="submitted").inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    with _lock:
        _jobs[job.id] = job
        _jobs_order.append(job.id)
    _persist(job)
    return job

# Worker integration placeholder (updated in Todo 22)

def get_job(job_id: str) -> ForensicsJob | None:
    return _jobs.get(job_id)


def list_jobs(modality: str | None = None, status: str | None = None, limit: int = 50) -> List[ForensicsJob]:
    with _lock:
        ids = list(reversed(_jobs_order))  # newest first
    out: List[ForensicsJob] = []
    for jid in ids:
        job = _jobs.get(jid)
        if not job:
            continue
        if modality and job.modality != modality:
            continue
        if status and job.status != status:
            continue
        out.append(job)
        if len(out) >= limit:
            break
    return out

__all__ = [
    "ForensicsJob",
    "submit_job",
    "get_job",
    "list_jobs",
]