"""Phase2 selective memory trigger scaffold.

Provides in-memory job queue & executor that simulates memory acquisition and enrichment.
Trigger conditions decided externally (pipeline) and call submit_memory_job(asset_id, context).
"""
from __future__ import annotations
import time, uuid, random
from typing import List, Dict, Any
from core import metrics

_JOBS: list[dict] = []  # ring buffer of recent jobs
_JOBS_MAX = 200
_ACTIVE = 0

async def submit_memory_job(asset_id: str, context: dict | None = None) -> dict:
    global _ACTIVE
    job_id = uuid.uuid4().hex[:12]
    rec = {
        "id": job_id,
        "asset_id": asset_id,
        "submitted": time.time(),
        "status": "pending",
        "context": context or {},
        "modality": "memory",
    }
    _JOBS.append(rec)
    if len(_JOBS) > _JOBS_MAX:
        del _JOBS[:-_JOBS_MAX]
    try:
        metrics.FORENSICS_JOB_TOTAL.labels(modality="memory", status="submitted").inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Simulate asynchronous acquisition (immediate for scaffold)
    _ACTIVE += 1
    try:
        await _execute(rec)
    finally:
        _ACTIVE -= 1
    return rec

async def _execute(rec: dict):
    try:
        rec["started"] = time.time()
        rec["status"] = "running"
        # Prefer real analysis via volatility3 when enabled and dump_path provided
        artifacts = []
        try:
            from config import runtime_params as _rp  # type: ignore
        except Exception:
            _rp = None  # type: ignore
        enabled = False
        try:
            enabled = bool(_rp.get_param("forensics.volatility.enabled")) if _rp else False
        except Exception:
            enabled = False
        dump_path = (rec.get("context") or {}).get("dump_path")
        if enabled and isinstance(dump_path, str) and dump_path:
            # Determine plugins & runtime budget
            try:
                plugins_param = _rp.get_param("forensics.volatility.plugins") if _rp else None
                if isinstance(plugins_param, str):
                    plugins = [p.strip() for p in plugins_param.split(',') if p.strip()]
                elif isinstance(plugins_param, list):
                    plugins = [str(p) for p in plugins_param]
                else:
                    plugins = ["windows.pslist", "windows.netscan"]
            except Exception:
                plugins = ["windows.pslist", "windows.netscan"]
            try:
                max_runtime_s = float(_rp.get_param("forensics.volatility.max_runtime_s") or 60.0) if _rp else 60.0
            except Exception:
                max_runtime_s = 60.0
            try:
                from forensics.volatility_analyzer import VolatilityAnalyzer  # type: ignore
                analyzer = VolatilityAnalyzer()
                res = analyzer.analyze(dump_path, plugins=plugins, max_runtime_s=max_runtime_s)
                artifacts = res.get("artifacts", [])
                rec["volatility_summary"] = res.get("summary", {})
            except Exception as e:
                rec.setdefault("warnings", []).append(f"volatility_error:{e}")
        # Optionally run YARA over extracted or provided paths when enabled
        try:
            yara_enabled = bool(_rp.get_param("forensics.yara.enabled")) if _rp else False
        except Exception:
            yara_enabled = False
        if yara_enabled:
            try:
                rules_dir = None
                try:
                    rules_dir = _rp.get_param("forensics.yara.rules_dir") if _rp else None
                except Exception:
                    rules_dir = None
                try:
                    y_max = float(_rp.get_param("forensics.yara.max_runtime_s") or 20.0) if _rp else 20.0
                except Exception:
                    y_max = 20.0
                # Determine files to scan: if volatility produced any artifacts with file paths, use them; otherwise, scan dump_path (if a file)
                scan_paths: list[str] = []
                try:
                    for a in artifacts:
                        p = ((a.get("data") or {}).get("filepath"))
                        if isinstance(p, str):
                            scan_paths.append(p)
                except Exception:
                    pass
                if not scan_paths:
                    dp = (rec.get("context") or {}).get("dump_path")
                    if isinstance(dp, str) and dp:
                        scan_paths.append(dp)
                if scan_paths:
                    from forensics.yara_scanner import scan as yara_scan  # type: ignore
                    yres = yara_scan(scan_paths, rules_dir=rules_dir, max_runtime_s=y_max)
                    yarts = yres.get("artifacts", [])
                    if yarts:
                        artifacts.extend(yarts)
                        rec["yara_summary"] = yres.get("summary", {})
            except Exception as e:
                rec.setdefault("warnings", []).append(f"yara_error:{e}")

        if not artifacts:
            # synthetic artifact fallback
            proc_count = random.randint(25, 120)
            suspicious = random.randint(0, 3)
            artifacts = [{
                "type": "synthetic.process_summary",
                "data": {
                    "process_count": proc_count,
                    "suspicious_modules": suspicious,
                    "open_sockets": random.randint(10, 200),
                },
                "severity": "low",
                "source": "simulated",
            }]
        rec["artifacts"] = artifacts
        rec["completed"] = time.time()
        rec["status"] = "done"
        # Persist simple custody chain per job (append-only JSONL with hash of artifact data)
        try:
            import hashlib, json as _json, pathlib as _pl
            cdir = _pl.Path("artifacts/forensics")
            cdir.mkdir(parents=True, exist_ok=True)
            cfile = cdir / "custody.jsonl"
            # build per-artifact hash
            for art in artifacts:
                payload = _json.dumps(art, sort_keys=True).encode("utf-8")
                h = hashlib.sha256(payload).hexdigest()
                with cfile.open('a', encoding='utf-8') as f:
                    f.write(_json.dumps({
                        "job_id": rec.get("id"),
                        "ts": time.time(),
                        "hash": h,
                        "type": art.get("type"),
                        "severity": art.get("severity"),
                    }) + "\n")
        except Exception:
            pass
        try:
            metrics.FORENSICS_JOB_TOTAL.labels(modality="memory", status="done").inc()  # type: ignore[attr-defined]
            metrics.FORENSICS_FINDINGS_TOTAL.labels(modality="memory").inc()  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        rec["status"] = "error"
        try:
            metrics.FORENSICS_JOB_TOTAL.labels(modality="memory", status="error").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

def recent_jobs(limit: int = 50):
    return list(_JOBS[-limit:])

__all__ = ["submit_memory_job", "recent_jobs"]
