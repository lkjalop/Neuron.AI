# Vulnerability Seeding and Matching (Operator Guide)

This guide shows how to seed the vulnerabilities table and trigger the matcher so that SBOM uploads produce persistent findings. Commands are for Windows PowerShell.

## Prerequisites
- Backend running (e.g., from repo root):
  - `cd src; uvicorn core.main:app --reload`
- Database configured (Postgres/Neon). One of:
  - `NEON_DATABASE_URL` or `DATABASE_URL` set
  - Or `repository.vuln.backend=postgres` in runtime params
- Admin API key in `ADMIN_API_KEY` env var or use the UI/API with header `X-API-Key`.

## Seed vulnerabilities

Option A: Use the default seed paths (first existing file is imported):

```powershell
$Headers = @{ 'X-API-Key' = $env:ADMIN_API_KEY }
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/admin/vuln/import" -Headers $Headers
```

Option B: Provide an explicit path (JSON or CSV):

```powershell
$Headers = @{ 'X-API-Key' = $env:ADMIN_API_KEY }
$Body = @{ path = "artifacts/vuln_catalog_seed.json" }
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/admin/vuln/import" -Headers $Headers -Body $Body
```

Notes:
- Supported files: `artifacts/vuln_catalog_seed.json`, `artifacts/vuln_catalog_enhanced.json`, `dump/vulns.json`, `dump/vulns.csv`.
- JSON may be an array or an object with `items`.

## Trigger the matcher

```powershell
$Headers = @{ 'X-API-Key' = $env:ADMIN_API_KEY }
$Body = @{ max_vulns = 1000 }
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/admin/vuln/match" -Headers $Headers -Body $Body
```

If Postgres is configured, matcher also runs automatically after each SBOM upload.

## Verify in the UI
- Open `frontend/vuln.html` (via your static hosting or development server).
- The banner at the top shows the source: Postgres/Memory/Mock.
- Upload a CycloneDX or SPDX SBOM; findings should appear. If seeded, the banner should show Postgres.

## Troubleshooting
- Ensure `asyncpg` is installed (already in `requirements.txt`).
- If the SSE stream import is missing, install `sse-starlette`.
- Check `audit/MIGRATION_AUDIT.log` for importer/matcher audit entries.
- DB connectivity check: `GET /health/ready` should be `ready` when fully configured.
