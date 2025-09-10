"""Lightweight tenant auth dependency."""
from __future__ import annotations
from fastapi import Header, HTTPException, status
from typing import Optional

TRUSTED_TENANTS = {"tenantA", "tenantB"}
API_KEYS = {  # placeholder mapping
    "demo-key-tenantA": "tenantA",
    "demo-key-tenantB": "tenantB",
}

async def tenant_dep(x_tenant_id: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)) -> str:
    tenant = None
    if x_api_key and x_api_key in API_KEYS:
        tenant = API_KEYS[x_api_key]
    elif x_tenant_id and x_tenant_id in TRUSTED_TENANTS:
        tenant = x_tenant_id
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant authentication required")
    return tenant

__all__ = ["tenant_dep"]
