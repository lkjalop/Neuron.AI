# Enterprise Compliance Modules Integration (from `dump/`)

This codebase includes enterprise-grade compliance artifacts under `dump/` (e.g., `enterprise_framework_router.py`). This doc explains safe, incremental ways to integrate them with Neuron.AI without destabilizing core paths.

## What we wired now
- Endpoints (best-effort):
  - `GET /enterprise/frameworks` — list available frameworks and capabilities.
  - `POST /enterprise/assess` — run a multi-framework assessment. Body:
    - `frameworks`: array of framework ids (e.g., `iso27001_ai`, `essential8`, `soc2`)
    - `documents`: object with evidence/doc references
    - `context`: org metadata
  - These dynamically import from `dump/enterprise_framework_router.py` if present; otherwise endpoints are absent.

## Suggested next steps
1. Evidence plumbing
   - Map `documents` to Neuron's retrieval pipeline; store pointers in `artifacts/` or DB.
   - Add an evidence index to support per-control drill-down in reports.
2. Persistence & audit
   - Create tables: `compliance_assessments`, `assessment_controls`, `assessment_artifacts`.
   - Write snapshots and append to `audit/COMPLIANCE_AUDIT.log`.
3. Reporting
   - Generate a `reports/compliance/` bundle with HTML/PDF outputs for auditor-ready packs.
4. Governance linking
   - Surface recommendations in `/governance/recommendations/recent` with a `category="compliance"` tag.
5. Scheduling
   - Optional weekly/monthly re-assess via `scheduler.report_scheduler`.

## Operational notes
- The integration is optional. If the `dump/` modules are removed, the app continues to run.
- For production readiness, move the modules from `dump/` to `src/compliance/` with tests and typed models.
