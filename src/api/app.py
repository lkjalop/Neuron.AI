from __future__ import annotations

import asyncio
from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional

from storage import postgres
from storage import vuln_store  # type: ignore
from storage.graph_store import neighbors, search_knowledge_articles, get_node
from storage.embedding_store import semantic_search
from services.embedding_service import text_to_vector
try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"  # type: ignore
    def generate_latest():  # type: ignore
        return b""

app = FastAPI(title="Neuron Vulnerability API", version="0.1.0")


@app.on_event("startup")
async def _startup():  # simple connectivity check (non-fatal)
    try:
        await postgres.health()
    except Exception:
        pass


@app.get("/health")
async def health():
    ok = await postgres.health()
    return {"status": "ok" if ok else "degraded"}


@app.get("/vulnerabilities")
async def list_vulnerabilities(severity: Optional[str] = None, exploit_only: bool = False, limit: int = 50):
    try:
        rows = await vuln_store.list_vulnerabilities(severity=severity, exploit_only=exploit_only, limit=limit)
        return {"items": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vulnerabilities/{cve_id}")
async def get_vulnerability(cve_id: str):
    v = await vuln_store.get_vulnerability(cve_id)
    if not v:
        raise HTTPException(status_code=404, detail="not found")
    return v


@app.get("/vuln/summary")
async def vuln_summary(limit: int = 100):
    """Aggregate vulnerability & finding stats for dashboards.

    Returns:
      total_vulnerabilities, exploit_available, kev_listed, avg_risk,
      top_risk (list[{cve_id, risk_score, severity}]), severity_counts,
      enrichment_coverage (epss_pct, kev_pct)
    """
    try:
        # Vulnerabilities
        vulns = await vuln_store.list_vulnerabilities(limit=limit)
        total = len(vulns)
        exploit = sum(1 for v in vulns if v.get("exploit_available"))
        kev = sum(1 for v in vulns if v.get("kev_listed"))
        epss_populated = sum(1 for v in vulns if v.get("epss") is not None)
        # Findings (reuse same list api for now; if high volume separate query)
        findings = []
        try:
            findings = await vuln_store.list_findings(limit=limit)  # type: ignore[attr-defined]
        except Exception:
            pass
        avg_risk = 0.0
        top = []
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
        scores = []
        for f in findings:
            rs = f.get("risk_score") or 0.0
            sev = (f.get("risk_severity") or "NONE").upper()
            if sev not in sev_counts:
                sev_counts[sev] = 0
            sev_counts[sev] += 1
            scores.append(rs)
        if scores:
            avg_risk = sum(scores) / len(scores)
        # Top risk findings by score
        top_findings = sorted([f for f in findings if f.get("risk_score") is not None], key=lambda x: x.get("risk_score"), reverse=True)[: min(10, len(findings))]
        for f in top_findings:
            top.append({
                "finding_id": f.get("id"),
                "cve_id": f.get("cve_id"),
                "risk_score": f.get("risk_score"),
                "severity": f.get("risk_severity"),
            })
        enrichment_cov = {
            "epss_pct": (epss_populated / total) * 100 if total else 0.0,
            "kev_pct": (kev / total) * 100 if total else 0.0,
        }
        return {
            "total_vulnerabilities": total,
            "exploit_available": exploit,
            "kev_listed": kev,
            "avg_risk": round(avg_risk, 4),
            "top_risk": top,
            "severity_counts": sev_counts,
            "enrichment_coverage": enrichment_cov,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/neighbors/{node_id}")
async def graph_neighbors(node_id: str, direction: str = Query("both", regex="^(in|out|both)$"), edge_type: Optional[str] = None, limit: int = 50):
    try:
        rows = await neighbors(node_id, direction=direction, edge_type=edge_type, limit=limit)
        return {"items": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/search")
async def knowledge_search(q: str, limit: int = 20):
    try:
        rows = await search_knowledge_articles(q, limit=limit)
        return {"items": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/semantic/search")
async def semantic_search_endpoint(q: str, limit: int = 10):
    vec = text_to_vector(q)
    try:
        hits = await semantic_search(vec, limit=limit)
        out = []
        for node_id, score in hits:
            node = await get_node(node_id)
            out.append({"node_id": node_id, "score": score, "node": node})
        return {"items": out, "count": len(out)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["app"]

@app.get("/metrics")
async def metrics_proxy():  # lightweight mirror for tests hitting api app directly
    try:
        data = generate_latest()  # type: ignore
        from fastapi import Response
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"metrics_error:{e}")
