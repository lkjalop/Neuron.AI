# Security Practices (Phase 2 Hardening / Pre-Persistence)

Status: Living document (Batch 2 secret & reliability scaffold)

## 1. Secrets Handling
- Source of Truth: Environment variables (12‑factor style). No secrets committed to repo.
- Loader: `config/secret_loader.get_secret(name, default=None, required=False)` returns value or raises if required.
- Fingerprinting: In `DEBUG` log level only, a fingerprint (first 4 + last 4 chars + length) is logged, never the raw secret.
- Rotation: Change env var and restart process. No in-app cache beyond Python process environment.
- Future Providers: Abstraction allows plugging in vaulted/KMS-backed retrieval without changing call sites.

### Required vs Optional
Use `required=True` only for hard runtime dependencies (e.g., future Neon DB password). Optional secrets should always have defensible degraded behavior.

### Prohibited Patterns
- Never print full secret to logs.
- Never embed tokens in tests or fixtures; use placeholders.
- Avoid long-lived API keys; plan upgrade to short‑TTL tokens + HMAC where possible.

## 2. Secret Scanning
Run the lightweight scanner before commit / in CI:
```
python scripts/scan_secrets.py
```
Exit Codes: 0 = none detected, 1 = potential matches (JWT, `npg_` Neon style token, long hex >64 chars).

False positives are acceptable; manually review flagged files. Extend patterns cautiously to avoid noise fatigue.

## 3. Configuration Governance
- Runtime parameters mutated only through audited endpoint `/admin/params/update` (HMAC/API key).
- All changes chained in `audit/param_changes.log` with head hash in `audit/param_changes.head`.
- Markdown mirror (`audit/AUDIT_LOG.md`) aids human review; tampering detectable via hash mismatch if chain is recomputed.

## 4. Audit & Integrity
- Canonical design doc (`docs/NEURON_PHASES.md`) hash persisted in `audit/CANONICAL_DOC_HASH`. Startup verifies unless `ALLOW_CANONICAL_DOC_DRIFT=true` (dev only).
- Feedback & anomaly evidence: append‑only JSONL logs hashed / referenced by manifests for reproducibility.
- Reliability artifacts: `scripts/verify_reliability_a11.py` produce structured evidence to avoid silent anomaly undercount.

## 5. Ingestion & Detection Reliability Guards
- Warm-up jitter (event skip + optional startup delay) prevents race conditions producing zero anomalies in first export.
- Inline detection (`x-inline-detect: true`) fast path guarded by runtime param `ingest.inline_detection.enabled`.
- `/admin/flush` deterministic drain ensures export scripts observe consistent end state.

## 6. Authentication & Authorization
- Current: Single admin API key + optional HMAC (timestamp + replay cache). Env vars: `ADMIN_API_KEY`, `ADMIN_HMAC_REQUIRED` (flag), `ADMIN_HMAC_DRIFT_SECONDS`.
- Planned: Per-tenant scoped keys, role-based separation (read-only vs mutation), key rotation schedule, and optional mTLS between internal services.

## 7. Logging & PII Minimization
- Analytical features expected numeric / anonymized. No raw user identifiers intentionally logged.
- Add redaction layer before introducing any free-form user content beyond analyst feedback (already length capped & hashed via chain).

## 8. Future Hardening Roadmap
| Area | Planned Enhancement | Rationale |
|------|---------------------|-----------|
| Secrets | Vault/KMS integration | Central rotation + access policy |
| Auth | Per-tenant keys + RBAC | Least privilege, audit clarity |
| Integrity | Signed manifests (ed25519) | Cryptographic tamper evidence |
| Persistence | Encrypted at rest (DB) | Regulatory & breach impact reduction |
| Transport | Enforce HTTPS/HSTS | MitM mitigation |
| Anomaly Log | Rotation + hash index | Size control + partial verification |
| Retrieval | Provenance signature | Guard poisoning / drift |
| Agents | Action allow-list policy | Prevent unauthorized autonomous changes |

## 9. Secure Development Practices
- Add new parameters only via `_SCHEMA` with bounded ranges to prevent silent extreme values.
- All new detectors must register explicit feature flags or strategy params before activation.
- Tests accompany new security-sensitive endpoints (auth permutations & failure modes).

## 10. Incident Response (Early Stage)
1. Detect anomaly or integrity mismatch (hash failure, unexpected secret exposure).
2. Triage: confirm environment vs code drift.
3. Contain: revoke/rotate implicated secret (`export OLD_KEY_REV=ts` optional variable for future automation).
4. Recover: redeploy with fresh env; regenerate reliability & integrity artifacts.
5. Postmortem: append Axx audit entry linking root cause & mitigation steps.

## 11. Contribution Guardrails
- No direct file edits to audit logs; always append with new section.
- Avoid adding large binary blobs; prefer summarized artifacts with hashes.
- Run tests + secret scan + lint (future) before PR.

---
Maintainer Note: Submit improvements as incremental sections referencing this doc in audit entries to preserve traceability.
