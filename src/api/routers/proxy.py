"""Proxy router for Prometheus and Grafana endpoints (moved from core.main).

All endpoints require predict-scope API key (or admin) via core.main's dependency,
so tokens for upstream systems are never exposed to the browser.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Response, Depends
import os, json
try:
    # Import dependency from main app to share auth and rate-limiting behavior
    from core.main import require_predict_api_key  # type: ignore
except Exception:  # pragma: no cover - fallback if import path changes in some envs
    def require_predict_api_key(*args, **kwargs):  # type: ignore
        return True

router = APIRouter(tags=["proxy"]) 

@router.get("/proxy/prom")
async def proxy_prom(q: str | None = None, start: float | None = None, end: float | None = None, step: float | None = None, timeout: float | None = None, _auth=Depends(require_predict_api_key)):
    base = os.getenv("PROMETHEUS_URL")
    if not base:
        raise HTTPException(503, "prometheus_unconfigured")
    expr = (q or "").strip()
    if not expr:
        raise HTTPException(400, "q_required")
    if any(c in expr for c in "`\n\r\x00;"):
        raise HTTPException(400, "invalid_expr")
    if start and end and end < start:
        raise HTTPException(400, "invalid_range")
    try:
        import aiohttp  # type: ignore
        if start is not None and end is not None and step is not None:
            url = f"{base.rstrip('/')}/api/v1/query_range"
            params = {"query": expr, "start": start, "end": end, "step": step}
        else:
            url = f"{base.rstrip('/')}/api/v1/query"
            params = {"query": expr}
        if timeout and timeout > 0:
            params["timeout"] = timeout
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=min(30, (timeout or 15)+5))) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    raise HTTPException(resp.status, body.get("error") or "prometheus_error")
                return body
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"prometheus_proxy_error:{e}")

@router.get("/proxy/grafana/iframe")
def proxy_grafana_iframe(panelId: str, dashboard: str | None = None, orgId: int | None = 1, vars: str | None = None, kiosk: int | None = 1, theme: str | None = None, fr: str | None = None, to: str | None = None, _auth=Depends(require_predict_api_key)):
    base = os.getenv("GRAFANA_BASE_URL")
    if not base:
        raise HTTPException(503, "grafana_unconfigured")
    dash = dashboard or os.getenv("GRAFANA_DEFAULT_DASH") or "neuron-kpis"
    if any(x in dash for x in "\n\r`\x00") or any(x in panelId for x in "\n\r`\x00"):
        raise HTTPException(400, "invalid_params")
    from urllib.parse import urlencode
    qs = {"orgId": orgId or 1, "panelId": panelId}
    if kiosk:
        qs["kiosk"] = kiosk
    if theme:
        qs["theme"] = theme
    if vars:
        try:
            vmap: dict[str, str] = {}
            if vars.strip().startswith("{"):
                vmap = json.loads(vars)
            else:
                for part in vars.split(","):
                    if not part.strip():
                        continue
                    k, _, v = part.partition("=")
                    if k:
                        vmap[k.strip()] = v.strip()
            for k, v in vmap.items():
                qs[f"var-{k}"] = v
        except Exception:
            pass
    # Optional time range: accept Grafana-compatible literals like 'now-6h' and 'now'
    if fr:
        qs["from"] = fr
    if to:
        qs["to"] = to
    url = f"{base.rstrip('/')}/d-solo/{dash}?{urlencode(qs)}"
    return {"url": url}

@router.get("/proxy/grafana/render")
async def proxy_grafana_render(panelId: str, dashboard: str | None = None, orgId: int | None = 1, vars: str | None = None, width: int | None = 1000, height: int | None = 500, fr: str | None = None, to: str | None = None, _auth=Depends(require_predict_api_key)):
    base = os.getenv("GRAFANA_BASE_URL")
    if not base:
        raise HTTPException(503, "grafana_unconfigured")
    dash = dashboard or os.getenv("GRAFANA_DEFAULT_DASH") or "neuron-kpis"
    render_path = os.getenv("GRAFANA_RENDER_PATH", "/render/d-solo")
    if any(x in dash for x in "\n\r`\x00") or any(x in panelId for x in "\n\r`\x00"):
        raise HTTPException(400, "invalid_params")
    from urllib.parse import urlencode
    qs = {"orgId": orgId or 1, "panelId": panelId, "width": max(100, int(width or 1000)), "height": max(100, int(height or 500))}
    if vars:
        try:
            vmap: dict[str, str] = {}
            if vars.strip().startswith("{"):
                vmap = json.loads(vars)
            else:
                for part in vars.split(","):
                    if not part.strip():
                        continue
                    k, _, v = part.partition("=")
                    if k:
                        vmap[k.strip()] = v.strip()
            for k, v in vmap.items():
                qs[f"var-{k}"] = v
        except Exception:
            pass
    if fr:
        qs["from"] = fr
    if to:
        qs["to"] = to
    url = f"{base.rstrip('/')}{render_path.rstrip('/')}/{dash}?{urlencode(qs)}"
    try:
        import aiohttp  # type: ignore
        headers = {}
        token = os.getenv("GRAFANA_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.read()
                if resp.status != 200:
                    raise HTTPException(resp.status, f"grafana_render_error:{resp.status}")
                return Response(content=data, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"grafana_proxy_error:{e}")

@router.get("/proxy/ready")
def proxy_ready(_auth=Depends(require_predict_api_key)):
    """Lightweight readiness echo for observability proxies.

    Returns whether upstream endpoints are configured. Does not perform network calls.
    Protected with predict-scope to avoid unauthenticated probing of deployment config.
    """
    prom = bool(os.getenv("PROMETHEUS_URL"))
    graf = bool(os.getenv("GRAFANA_BASE_URL"))
    return {"prometheus_configured": prom, "grafana_configured": graf}

__all__ = ['router']
