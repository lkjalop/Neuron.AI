"""Simple structured migration runner.

Stores applied migrations in table `schema_migrations` (id TEXT PRIMARY KEY, applied_at DOUBLE PRECISION).
Each migration is an async function applied in order; idempotent DDL guarded with IF NOT EXISTS / ON CONFLICT.
"""
from __future__ import annotations

import time
from typing import List, Callable, Awaitable
import sys

MIGRATIONS: List[tuple[str, Callable[[], Awaitable[None]]]] = []


def migration(id_: str):  # decorator
    def wrap(fn: Callable[[], Awaitable[None]]):
        MIGRATIONS.append((id_, fn))
        return fn
    return wrap


def _get_postgres():
    """Return a postgres shim, honoring test monkeypatches.

    Tests may insert a non-module object into sys.modules['storage.postgres'].
    Using standard importlib can bypass that, so prefer sys.modules if present.
    """
    pg = sys.modules.get("storage.postgres")
    if pg is not None:
        return pg
    # Fallback to real module
    from storage import postgres as real_pg  # type: ignore
    return real_pg


@migration("0001_init_anomalies")
async def _m0001():  # noqa: D401
    postgres = _get_postgres()
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            tenant TEXT,
            detector TEXT,
            score DOUBLE PRECISION,
            fusion_score DOUBLE PRECISION,
            event_time DOUBLE PRECISION,
            payload JSONB
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_event_time ON anomalies (event_time)")
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_tenant ON anomalies (tenant)")


@migration("0002_calibration_quantiles")
async def _m0002():
    postgres = _get_postgres()
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_quantiles (
            tenant TEXT PRIMARY KEY,
            p50 DOUBLE PRECISION,
            p90 DOUBLE PRECISION,
            p99 DOUBLE PRECISION,
            updated DOUBLE PRECISION
        )
        """
    )


async def apply_migrations():
    postgres = _get_postgres()
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at DOUBLE PRECISION
        )
        """
    )
    rows = await postgres.fetch("SELECT id FROM schema_migrations")
    applied = {r[0] for r in rows}
    for mid, fn in MIGRATIONS:
        if mid in applied:
            continue
        try:
            await fn()
            await postgres.execute("INSERT INTO schema_migrations (id, applied_at) VALUES ($1,$2)", mid, time.time())
        except Exception:  # noqa: BLE001
            # continue; migration failures are non-fatal at this stage
            continue

__all__ = ["apply_migrations"]


@migration("0003_vuln_scanning")
async def _m0003():
    postgres = _get_postgres()
    # assets table
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            name TEXT,
            kind TEXT,
            metadata JSONB,
            discovered_at DOUBLE PRECISION
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets (kind)")

    # components (SBOM)
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS sbom_components (
            id TEXT PRIMARY KEY,
            name TEXT,
            version TEXT,
            purl TEXT,
            ecosystem TEXT,
            raw_json JSONB
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_sbom_components_name ON sbom_components (name)")

    # asset -> component mapping
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_components (
            asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
            component_id TEXT REFERENCES sbom_components(id) ON DELETE CASCADE,
            PRIMARY KEY(asset_id, component_id)
        )
        """
    )

    # vulnerabilities
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            cve_id TEXT PRIMARY KEY,
            aliases TEXT[],
            cvss_base DOUBLE PRECISION,
            cvss_vector TEXT,
            severity TEXT,
            cwe_ids TEXT[],
            published_ts DOUBLE PRECISION,
            modified_ts DOUBLE PRECISION,
            exploit_available BOOLEAN,
            epss DOUBLE PRECISION,
            kev_listed BOOLEAN,
            raw_json JSONB
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_vuln_severity ON vulnerabilities (severity)")

    # findings (vuln present on asset/component)
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            cve_id TEXT REFERENCES vulnerabilities(cve_id) ON DELETE CASCADE,
            asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
            component_id TEXT REFERENCES sbom_components(id) ON DELETE SET NULL,
            first_seen DOUBLE PRECISION,
            last_seen DOUBLE PRECISION,
            state TEXT,
            detection_source TEXT,
            risk_score DOUBLE PRECISION,
            risk_severity TEXT,
            asset_metadata JSONB
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_findings_asset ON findings (asset_id)")
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_findings_cve ON findings (cve_id)")

    # finding_events (history / transitions)
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_events (
            id TEXT PRIMARY KEY,
            finding_id TEXT REFERENCES findings(id) ON DELETE CASCADE,
            event_ts DOUBLE PRECISION,
            event_type TEXT,
            payload JSONB
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_finding_events_finding ON finding_events (finding_id)")


@migration("0004_vuln_enrichment_extensions")
async def _m0004():
    postgres = _get_postgres()
    # Add enrichment timestamp columns if not present
    try:
        await postgres.execute("ALTER TABLE vulnerabilities ADD COLUMN IF NOT EXISTS enrichment_epss_ts DOUBLE PRECISION")
    except Exception:
        pass
    try:
        await postgres.execute("ALTER TABLE vulnerabilities ADD COLUMN IF NOT EXISTS enrichment_kev_ts DOUBLE PRECISION")
    except Exception:
        pass
    # Feed state tracking table (etag, last fetch, status)
    await postgres.execute(
        """
        CREATE TABLE IF NOT EXISTS feed_state (
            feed_name TEXT PRIMARY KEY,
            etag TEXT,
            last_fetch_ts DOUBLE PRECISION,
            last_status TEXT,
            last_error TEXT
        )
        """
    )
    await postgres.execute("CREATE INDEX IF NOT EXISTS idx_feed_state_status ON feed_state (last_status)")


@migration("0005_vuln_sla_columns")
async def _m0005():
    postgres = _get_postgres()
    # Add sla_due_ts column to findings for SLA breach tracking
    try:
        await postgres.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS sla_due_ts DOUBLE PRECISION")
    except Exception:
        pass

@migration("0006_finding_risk_factors")
async def _m0006():
    postgres = _get_postgres()
    try:
        await postgres.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS risk_factors JSONB")
    except Exception:
        pass

@migration("0007_feature_series")
async def _m0007():
    postgres = _get_postgres()
    # Temporal feature vectors per asset/kind
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_series (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                ts DOUBLE PRECISION NOT NULL,
                vector JSONB NOT NULL,
                version INTEGER DEFAULT 1,
                created_ts DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
            )
            """
        )
    except Exception:
        pass
    try:
        await postgres.execute("CREATE INDEX IF NOT EXISTS idx_feature_series_asset_kind_ts ON feature_series (asset_id, kind, ts DESC)")
    except Exception:
        pass

@migration("0008_attack_mapping")
async def _m0008():
    postgres = _get_postgres()
    # ATT&CK technique table
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS attack_techniques (
                technique_id TEXT PRIMARY KEY,
                name TEXT,
                tactic TEXT,
                description TEXT
            )
            """
        )
    except Exception:
        pass

@migration("0009_remediation_workflow")
async def _m0009():
    postgres = _get_postgres()
    # Add remediation workflow fields to findings
    statements = [
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS treatment_state TEXT",
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS accepted_risk BOOLEAN",
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS remediation_target_ts DOUBLE PRECISION",
    ]
    for stmt in statements:
        try:
            await postgres.execute(stmt)
        except Exception:  # noqa: BLE001
            pass

@migration("0010_risk_exceptions")
async def _m0010():
    postgres = _get_postgres()
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS exceptions (
                id TEXT PRIMARY KEY,
                finding_id TEXT REFERENCES findings(id) ON DELETE CASCADE,
                created_ts DOUBLE PRECISION,
                expires_ts DOUBLE PRECISION,
                reason TEXT,
                approved_by TEXT,
                status TEXT
            )
            """
        )
    except Exception:
        pass
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS exception_events (
                id TEXT PRIMARY KEY,
                exception_id TEXT REFERENCES exceptions(id) ON DELETE CASCADE,
                event_ts DOUBLE PRECISION,
                event_type TEXT,
                payload TEXT
            )
            """
        )
    except Exception:
        pass
    try:
        await postgres.execute("CREATE INDEX IF NOT EXISTS idx_exceptions_finding ON exceptions (finding_id)")
    except Exception:
        pass

@migration("0011_asset_external_exposure")
async def _m0011():
    postgres = _get_postgres()
    try:
        await postgres.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS external_exposure BOOLEAN")
    except Exception:  # noqa: BLE001
        pass

@migration("0012_feed_confidence")
async def _m0012():
    postgres = _get_postgres()
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_confidence (
                feed_name TEXT PRIMARY KEY,
                weight DOUBLE PRECISION,
                updated_ts DOUBLE PRECISION
            )
            """
        )
    except Exception:  # noqa: BLE001
        pass
    # Software (tool / malware) table
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS attack_software (
                software_id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                description TEXT
            )
            """
        )
    except Exception:
        pass
    # Vulnerability ↔ software mapping (many-to-many)
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS vuln_software_map (
                cve_id TEXT REFERENCES vulnerabilities(cve_id) ON DELETE CASCADE,
                software_id TEXT REFERENCES attack_software(software_id) ON DELETE CASCADE,
                PRIMARY KEY (cve_id, software_id)
            )
            """
        )
    except Exception:
        pass
    # Technique ↔ software mapping
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS software_technique_map (
                software_id TEXT REFERENCES attack_software(software_id) ON DELETE CASCADE,
                technique_id TEXT REFERENCES attack_techniques(technique_id) ON DELETE CASCADE,
                PRIMARY KEY (software_id, technique_id)
            )
            """
        )
    except Exception:
        pass

@migration("0013_remediation_plans")
async def _m0013():
    postgres = _get_postgres()
    try:
        await postgres.execute(
            """
            CREATE TABLE IF NOT EXISTS remediation_plans (
                id TEXT PRIMARY KEY,
                created_ts DOUBLE PRECISION,
                plan_hash TEXT,
                content JSONB,
                signed_by TEXT,
                signature TEXT
            )
            """
        )
    except Exception:  # noqa: BLE001
        pass

@migration("0015_findings_composite_indexes")
async def _m0015():
    """Add composite indexes to accelerate common read paths for findings and vulnerabilities.

    - findings(state, risk_severity, last_seen DESC)
    - findings(asset_id, state, last_seen DESC)
    - vulnerabilities(kev_listed, exploit_available)
    """
    postgres = _get_postgres()
    try:
        await postgres.execute("CREATE INDEX IF NOT EXISTS idx_findings_state_sev_last ON findings (state, risk_severity, last_seen DESC)")
    except Exception:
        pass
    try:
        await postgres.execute("CREATE INDEX IF NOT EXISTS idx_findings_asset_state_last ON findings (asset_id, state, last_seen DESC)")
    except Exception:
        pass
    try:
        await postgres.execute("CREATE INDEX IF NOT EXISTS idx_vuln_kev_exploit ON vulnerabilities (kev_listed, exploit_available)")
    except Exception:
        pass
