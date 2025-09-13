from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Any
import json as _json
import pathlib as _pl
import hashlib as _hashlib

router = APIRouter()


@router.post("/forensics/jobs")
async def forensics_submit(body: dict):
    modality = (body or {}).get("modality") or "memory"
    params = (body or {}).get("params") or {}
    try:
        from core.forensics import jobs as fj  # type: ignore
        job = await fj.submit_job(modality, params)
        return {"job": job.to_record()}
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"submit_error:{e}")


@router.get("/forensics/jobs/{job_id}")
def forensics_get(job_id: str):
    try:
        from core.forensics import jobs as fj  # type: ignore
        job = fj.get_job(job_id)
        if not job:
            raise HTTPException(404, "job_not_found")
        return {"job": job.to_record()}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"get_error:{e}")


@router.get("/forensics/jobs")
def forensics_list(modality: str | None = None, status: str | None = None, limit: int = 50):
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50
    try:
        from core.forensics import jobs as fj  # type: ignore
        jobs = fj.list_jobs(modality=modality, status=status, limit=limit)
        return {"items": [j.to_record() for j in jobs], "count": len(jobs)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"list_error:{e}")


@router.get("/forensics/custody/verify")
def forensics_custody_verify(job_id: str):
    """Verify custody hashes by comparing persisted chain with recomputed hashes."""
    try:
        from core.forensics import jobs as fj  # type: ignore
        job = fj.get_job(job_id)
        if not job:
            raise HTTPException(404, "job_not_found")
        rec = job.to_record()
        artifacts = ((rec.get("result") or {}).get("artifacts") or [])
        cfile = _pl.Path("artifacts/forensics/custody.jsonl")
        chain = []
        if cfile.exists():
            try:
                with cfile.open('r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            o = _json.loads(line)
                        except Exception:
                            continue
                        if o.get("job_id") == job_id:
                            chain.append(o)
            except Exception:
                pass
        # recompute
        recomputed = []
        for art in artifacts:
            try:
                payload = _json.dumps(art, sort_keys=True).encode("utf-8")
                h = _hashlib.sha256(payload).hexdigest()
                recomputed.append(h)
            except Exception:
                recomputed.append(None)
        chain_hashes = [c.get("hash") for c in chain if isinstance(c.get("hash"), str)]
        set_chain = set(chain_hashes)
        set_re = set([h for h in recomputed if isinstance(h, str)])
        matches = len(set_chain.intersection(set_re))
        mismatches = len(set_chain.symmetric_difference(set_re))
        sample_mismatch = list(set_chain.symmetric_difference(set_re))[:5]
        return {
            "job_id": job_id,
            "artifacts_count": len(artifacts),
            "chain_count": len(chain_hashes),
            "matches": matches,
            "mismatches": mismatches,
            "mismatch_samples": sample_mismatch,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"verify_error:{e}")


@router.get("/forensics/jobs/{job_id}/artifacts/download")
def forensics_artifacts_download(job_id: str):
    """Package job result artifacts into a temporary JSON file for download."""
    try:
        from core.forensics import jobs as fj  # type: ignore
        job = fj.get_job(job_id)
        if not job:
            raise HTTPException(404, "job_not_found")
        rec = job.to_record()
        arts = ((rec.get("result") or {}).get("artifacts") or [])
        if not arts:
            res = rec.get("result")
            if res:
                arts = [res]
        if not arts:
            raise HTTPException(404, "no_artifacts")
        base = _pl.Path("artifacts/forensics/downloads")
        base.mkdir(parents=True, exist_ok=True)
        fname = base / f"{job_id}_artifacts.json"
        with fname.open('w', encoding='utf-8') as f:
            _json.dump({"job_id": job_id, "artifacts": arts}, f, ensure_ascii=False, indent=2)
        return FileResponse(str(fname), media_type='application/json', filename=fname.name)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"download_error:{e}")


@router.get("/forensics/jobs/recent")
def forensics_jobs_recent(limit: int = 50):
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50
    try:
        from core.forensics import jobs as fj  # type: ignore
        items = [j.to_record() for j in fj.list_jobs(limit=limit)]
        return {"items": items, "count": len(items)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"recent_error:{e}")
