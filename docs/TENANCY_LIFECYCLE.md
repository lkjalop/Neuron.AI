# Tenancy Lifecycle (Onboarding, Offboarding, Secure Deletion)

This document outlines how to onboard new clients (tenants), manage their data isolation, and safely offboard / purge data upon request.

## 1. Concepts
- Tenant: Logical isolation boundary (org / customer). Identified by `tenant_id` (UUID recommended).
- Project: Sub-scope within a tenant (environment, business unit). `project_id` references tenant.
- Data Domains: retrieval chunks, assets, vulnerabilities, detections, reports, metrics (ephemeral), audit chain.
- Encryption: At-rest encryption keyed per tenant (KMS or envelope key pattern) – FUTURE.

## 2. Onboarding Flow
1. Generate `tenant_id` and store minimal record (name, created_at, status=active).
2. Provision API keys / service tokens (scoped, revocable) with roles (admin, analyst, viewer).
3. Initialize parameter namespace defaults (prefix: `tenant.<tenant_id>.*`).
4. (Optional) Pre-create logical schemas / table partitions (PostgreSQL: separate schema per tenant; SQLite fallback: namespace prefix fields like `tenant_id` column).
5. Register default retention + generation settings.
6. Schedule initial ingestion discovery tasks (vuln import, asset inventory baseline).
7. Emit audit log entry: `TENANT_ONBOARD` with hash chaining.

## 3. Data Isolation Strategy
| Layer | Strategy (MVP) | Future Hardening |
|-------|----------------|------------------|
| DB (SQLite current) | Shared tables + `tenant_id` column | Move to Postgres; schema-per-tenant or row-level security |
| File Artifacts | Directory prefix: `artifacts/<tenant_id>/...` | KMS envelope keys per directory |
| Retrieval Chunks | Add `tenant_id` column and composite indexes | Vector store w/ per-tenant collections |
| Metrics | Labeled by `tenant` where applicable | Multi-tenant Prometheus with federation |
| Audit | Global log referencing `tenant_id` | Per-tenant cryptographic transparency log |

## 4. Offboarding (Soft Disable)
1. Mark tenant status = `disabled` (no new ingestion / queries allowed).
2. Revoke active API keys (invalidate tokens; add to denylist cache).
3. Export data snapshot (optional, encrypted ZIP) if requested.
4. Wait (configurable cooling period) before hard deletion to prevent accidental loss (e.g., 7 days).
5. Emit audit event: `TENANT_DISABLE_REQUEST`.

## 5. Secure Deletion (Hard Purge)
Steps (idempotent, transactional best-effort):
```
BEGIN
  DELETE FROM retrieval_chunks WHERE tenant_id = ?;
  DELETE FROM vulnerabilities WHERE tenant_id = ?;
  DELETE FROM assets WHERE tenant_id = ?;
  DELETE FROM detections WHERE tenant_id = ?;
  DELETE FROM reports WHERE tenant_id = ?;
  DELETE FROM param_store WHERE tenant_id = ?; -- if tenant-scoped params
  DELETE FROM audit_log WHERE tenant_id = ?;   -- if per-tenant slices (retain MANIFEST chain pivot)
  Filesystem: rm -rf artifacts/<tenant_id>/
COMMIT
Wipe pass (optional): overwrite large artifact files before delete
Emit audit: TENANT_PURGE_COMPLETE
```
If encryption-at-rest with per-tenant DEK: destroy DEK first (crypto-delete) then lazily GC physical bits.

## 6. Legal / Compliance Considerations
- Right to Erasure (GDPR): Provide self-service purge request endpoint; must confirm via signed challenge.
- Data Residency: Tag tenant with region; restrict processing nodes.
- Audit Integrity: Keep tombstone manifest entry referencing purged tenant id & timestamp without retaining content.
- Retention Policy Overrides: Tenant may configure reduced max_age; system must not retain beyond contract period.

## 7. Operational Safeguards
- Dry-run purge mode (counts rows/files, no mutation) for confirmation.
- Minimum 2-step confirmation: `initiate` → `confirm(token)`.
- Rate limit purge operations (avoid mass destructive batch).
- Automatic backup snapshot prior to purge (encrypted) with auto-expire.

## 8. API Surface (Proposed)
| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/tenants` | POST | Create tenant | Admin global |
| `/tenants/{id}` | GET | Get tenant metadata | Tenant admin |
| `/tenants/{id}/disable` | POST | Soft disable | Tenant admin |
| `/tenants/{id}/purge` | POST | Initiate purge (dry_run flag) | Platform admin |
| `/tenants/{id}/purge/confirm` | POST | Confirm irreversible purge | Platform admin |

## 9. Background Tasks
- Purge garbage collector scans for `pending_purge` tenants older than cooling period; executes deletion.
- Retention monitor enforces tenant-specific retention overrides.

## 10. Telemetry / Metrics Additions (Future)
- `tenant_purge_requests_total{status}`
- `tenant_purge_duration_seconds` (histogram)
- `tenant_data_volume_bytes` gauge per domain (pre-purge measurement)

## 11. Migration Steps to Introduce Tenancy
1. Add `tenant_id` column to existing tables (NULL allowed initially) + backfill default.
2. Update code paths to always scope by active tenant (middleware injection).
3. Add composite indexes: `(tenant_id, created_at)` for time-prunable tables.
4. Enforce queries supply tenant context (assert guard).
5. Introduce API key mapping: key_hash -> tenant_id.

## 12. Offboarding Checklist
- [ ] Disable ingestion connectors
- [ ] Revoke keys
- [ ] Snapshot export (if requested)
- [ ] Cooling period timer started
- [ ] Purge executed / manifest updated
- [ ] Confirmation sent / ticket closed

## 13. Future Hardening
- WORM (Write Once Read Many) append-only audit segments
- Transparency log anchoring in public chain (periodic root hash)
- Secure multi-party purge approval workflow

---
This lifecycle spec will be iteratively refined as multi-tenancy code is introduced.
