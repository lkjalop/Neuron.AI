"""Persistence helpers for vulnerability scanning domain.

Provides lightweight async helpers wrapping the generic asyncpg wrapper in
`storage.postgres` (lazy initialized). All helpers are best‑effort: if the
database layer is not configured (no NEON_DATABASE_URL) they will raise the
underlying RuntimeError to the caller so the caller can decide to fall back
to in‑memory operation.

Tables expected (created by migration 0003_vuln_scanning):
 - vulnerabilities
 - findings

Only the subset of fields currently produced by the scanner agent / normalizers
are persisted. Additional enrichment fields (EPSS, KEV etc.) can be added later
without breaking contract by extending the UPSERT SET list.

Contract (initial):
 - upsert_vulnerability(Vulnerability) : stores/updates vulnerability row
 - upsert_vulnerabilities(iterable)    : bulk convenience (sequential for now)
 - list_findings(severity?, asset_id?, limit) : recent findings ordered by last_seen
 - get_vulnerability(cve_id) : fetch single vulnerability (dict) or None

NOTE: Finding creation is not yet performed here; a later task will integrate
the scanner agent to create/update findings and then risk scores will be
updated in persistence. For now list_findings simply returns what is in the
database (likely empty until that integration lands).
"""
from __future__ import annotations

from typing import Iterable, List, Dict, Any, Optional
from dataclasses import asdict
import json
import time
import datetime as _dt
import hashlib
import logging

from scanner.version_applicability import any_cpe_match_applies  # type: ignore
from core.metrics import VULN_VERSION_FILTERED_TOTAL  # type: ignore
try:
    from core.metrics import VULN_OSV_ALIAS_HITS_TOTAL  # type: ignore
except Exception:  # noqa: BLE001
    VULN_OSV_ALIAS_HITS_TOTAL = None  # type: ignore
try:
    from core.metrics import VULN_MATCH_BATCH_TRUNCATED_TOTAL  # type: ignore
except Exception:  # noqa: BLE001
    VULN_MATCH_BATCH_TRUNCATED_TOTAL = None  # type: ignore
try:
    from scanner.osv_batch import fetch_osv_aliases  # type: ignore
except Exception:  # noqa: BLE001
    fetch_osv_aliases = None  # type: ignore
from config.runtime_params import runtime_params  # type: ignore

log = logging.getLogger("vuln.match")

from scanner.models import Vulnerability  # type: ignore

from . import postgres  # local lazy pool


async def upsert_vulnerability(v: Vulnerability) -> None:
    """Insert or update a vulnerability record.

    ON CONFLICT strategy updates mutable descriptive fields while retaining
    the original published_ts (unless changed upstream) and always refreshing
    modified_ts & raw_json.
    """
    await postgres.execute(
        """
        INSERT INTO vulnerabilities (
            cve_id, aliases, cvss_base, cvss_vector, severity, cwe_ids,
            published_ts, modified_ts, exploit_available, epss, kev_listed, raw_json
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (cve_id) DO UPDATE SET
            aliases=EXCLUDED.aliases,
            cvss_base=EXCLUDED.cvss_base,
            cvss_vector=EXCLUDED.cvss_vector,
            severity=EXCLUDED.severity,
            modified_ts=EXCLUDED.modified_ts,
            exploit_available=EXCLUDED.exploit_available,
            epss=EXCLUDED.epss,
            kev_listed=EXCLUDED.kev_listed,
            raw_json=EXCLUDED.raw_json
        """,
        v.cve_id,
        v.aliases,
        v.cvss_base,
        v.cvss_vector,
        v.severity,
        v.cwe_ids,
        _to_ts(v.published_ts),
        _to_ts(v.modified_ts),
        v.exploit_available,
        v.epss,
        v.kev_listed,
        json.dumps(v.raw_json),
    )


async def upsert_vulnerabilities(vulns: Iterable[Vulnerability]) -> int:
    """Bulk convenience wrapper; sequential for now (low volume expectation).

    Returns number of vulnerabilities processed.
    """
    count = 0
    for v in vulns:
        try:
            await upsert_vulnerability(v)
            count += 1
        except Exception:
            # Best-effort: continue on individual failure
            continue
    return count


async def get_vulnerability(cve_id: str) -> Optional[Dict[str, Any]]:
    rows = await postgres.fetch("SELECT * FROM vulnerabilities WHERE cve_id=$1", cve_id)
    if not rows:
        return None
    return _row_to_dict(rows[0])


async def list_findings(severity: str | None = None, asset_id: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    clauses = []
    args: List[Any] = []  # type: ignore[assignment]
    if severity:
        clauses.append("risk_severity=$%d" % (len(args) + 1))
        args.append(severity.upper())
    if asset_id:
        clauses.append("asset_id=$%d" % (len(args) + 1))
        args.append(asset_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM findings {where} ORDER BY last_seen DESC LIMIT $%d" % (len(args) + 1)
    args.append(limit)
    rows = await postgres.fetch(sql, *args)
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> Dict[str, Any]:  # asyncpg Record provides mapping interface
    try:
        return dict(row)
    except Exception:
        # Fallback: assume sequence-like
        return {str(i): row[i] for i in range(len(row))}


def _to_ts(dt: _dt.datetime | None) -> Optional[float]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.timestamp()


__all__ = [
    "upsert_vulnerability",
    "upsert_vulnerabilities",
    "get_vulnerability",
    "list_findings",
]

# --- New Finding helpers & vulnerability listing ---

async def upsert_finding(rec: Dict[str, Any]) -> None:
    """Upsert a finding record.

    Expected keys (subset enforced): id, cve_id, asset_id, component_id, first_seen,
    last_seen, state, detection_source, risk_score, risk_severity, asset_metadata.
    Timestamps should be float epoch seconds.
    """
    await postgres.execute(
        """
        INSERT INTO findings (
            id, cve_id, asset_id, component_id, first_seen, last_seen, state,
            detection_source, risk_score, risk_severity, asset_metadata, sla_due_ts, risk_factors,
            treatment_state, accepted_risk, remediation_target_ts
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        ON CONFLICT (id) DO UPDATE SET
            last_seen=EXCLUDED.last_seen,
            state=EXCLUDED.state,
            risk_score=EXCLUDED.risk_score,
            risk_severity=EXCLUDED.risk_severity,
            asset_metadata=EXCLUDED.asset_metadata,
            sla_due_ts=COALESCE(findings.sla_due_ts, EXCLUDED.sla_due_ts),
            risk_factors=COALESCE(EXCLUDED.risk_factors, findings.risk_factors),
            treatment_state=COALESCE(EXCLUDED.treatment_state, findings.treatment_state),
            accepted_risk=COALESCE(EXCLUDED.accepted_risk, findings.accepted_risk),
            remediation_target_ts=COALESCE(EXCLUDED.remediation_target_ts, findings.remediation_target_ts)
        """,
        rec.get("id"),
        rec.get("cve_id"),
        rec.get("asset_id"),
        rec.get("component_id"),
        rec.get("first_seen"),
        rec.get("last_seen"),
        rec.get("state"),
        rec.get("detection_source"),
        rec.get("risk_score"),
        rec.get("risk_severity"),
        rec.get("asset_metadata"),
        rec.get("sla_due_ts"),
        json.dumps(rec.get("risk_factors") or {}),
        rec.get("treatment_state"),
        rec.get("accepted_risk"),
        rec.get("remediation_target_ts"),
    )

async def bulk_upsert_findings(recs: List[Dict[str, Any]]):
    """Bulk upsert findings in a single transaction using executemany pattern.

    Falls back silently if any error occurs (best-effort semantics consistent
    with individual upsert). Expects each rec to contain same keys as upsert_finding.
    """
    if not recs:
        return 0
    rows = [(
        r.get("id"), r.get("cve_id"), r.get("asset_id"), r.get("component_id"), r.get("first_seen"), r.get("last_seen"),
        r.get("state"), r.get("detection_source"), r.get("risk_score"), r.get("risk_severity"), r.get("asset_metadata"),
        r.get("sla_due_ts"), json.dumps(r.get("risk_factors") or {}), r.get("treatment_state"), r.get("accepted_risk"), r.get("remediation_target_ts")
    ) for r in recs]
    try:
        await postgres.executemany(
            """
            INSERT INTO findings (
                id, cve_id, asset_id, component_id, first_seen, last_seen, state,
                detection_source, risk_score, risk_severity, asset_metadata, sla_due_ts, risk_factors,
                treatment_state, accepted_risk, remediation_target_ts
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            ON CONFLICT (id) DO UPDATE SET
                last_seen=EXCLUDED.last_seen,
                state=EXCLUDED.state,
                risk_score=EXCLUDED.risk_score,
                risk_severity=EXCLUDED.risk_severity,
                asset_metadata=EXCLUDED.asset_metadata,
                sla_due_ts=COALESCE(findings.sla_due_ts, EXCLUDED.sla_due_ts),
                risk_factors=COALESCE(EXCLUDED.risk_factors, findings.risk_factors),
                treatment_state=COALESCE(EXCLUDED.treatment_state, findings.treatment_state),
                accepted_risk=COALESCE(EXCLUDED.accepted_risk, findings.accepted_risk),
                remediation_target_ts=COALESCE(EXCLUDED.remediation_target_ts, findings.remediation_target_ts)
            """,
            rows,
        )
    except Exception:
        # Best-effort fallback: attempt sequential inserts
        for r in recs:
            try:
                await upsert_finding(r)
            except Exception:
                continue
    return len(recs)

__all__.append("bulk_upsert_findings")


async def list_vulnerabilities(severity: str | None = None, exploit_only: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
    clauses = []
    args: List[Any] = []  # type: ignore[assignment]
    if severity:
        clauses.append("severity=$%d" % (len(args) + 1))
        args.append(severity.upper())
    if exploit_only:
        clauses.append("exploit_available=true")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM vulnerabilities {where} ORDER BY published_ts DESC NULLS LAST LIMIT $%d" % (len(args) + 1)
    args.append(limit)
    rows = await postgres.fetch(sql, *args)
    return [_row_to_dict(r) for r in rows]

__all__.extend(["upsert_finding", "list_vulnerabilities"])

# --- Asset & Component (SBOM) helpers ---

async def upsert_asset(asset: Dict[str, Any]) -> None:
    """Insert or update an asset record.

    Expected keys: id, name, kind, metadata (dict), discovered_at (epoch seconds optional).
    """
    await postgres.execute(
        """
        INSERT INTO assets (id, name, kind, metadata, discovered_at, external_exposure)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name,
            kind=EXCLUDED.kind,
            metadata=EXCLUDED.metadata,
            external_exposure=COALESCE(EXCLUDED.external_exposure, assets.external_exposure)
        """,
        asset.get("id"),
        asset.get("name"),
        asset.get("kind"),
        json.dumps(asset.get("metadata") or {}),
        asset.get("discovered_at"),
        asset.get("external_exposure"),
    )


async def upsert_component(comp: Dict[str, Any]) -> None:
    """Insert or update a software component (SBOM) record.

    Expected keys: id, name, version, purl, ecosystem, raw_json (dict)
    """
    # Infer ecosystem from purl if not provided
    try:
        if not comp.get("ecosystem") and comp.get("purl"):
            # Simple purl parse: pkg:type/name@version or pkg:type/namespace/name@version
            purl = comp.get("purl")
            # Strip leading pkg: if present
            if purl.startswith("pkg:" ):
                rem = purl[4:]
            else:
                rem = purl
            # Split type and rest
            if '/' in rem:
                type_part, rest = rem.split('/', 1)
            else:
                type_part, rest = rem, ''
            eco_map = {
                'npm': 'NPM',
                'pypi': 'PyPI',
                'maven': 'Maven',
                'gem': 'RubyGems',
                'rubygems': 'RubyGems',
                'cargo': 'Crates',
                'crates': 'Crates',
                'golang': 'Go',
            }
            inferred = eco_map.get(type_part.lower())
            if inferred:
                comp["ecosystem"] = inferred
    except Exception:
        pass
    await postgres.execute(
        """
        INSERT INTO sbom_components (id, name, version, purl, ecosystem, raw_json)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name,
            version=EXCLUDED.version,
            purl=EXCLUDED.purl,
            ecosystem=EXCLUDED.ecosystem,
            raw_json=EXCLUDED.raw_json
        """,
        comp.get("id"),
        comp.get("name"),
        comp.get("version"),
        comp.get("purl"),
        comp.get("ecosystem"),
        json.dumps(comp.get("raw_json") or {}),
    )


async def link_asset_component(asset_id: str, component_id: str) -> None:
    """Ensure mapping row exists between an asset and component."""
    await postgres.execute(
        """
        INSERT INTO asset_components (asset_id, component_id)
        VALUES ($1,$2)
        ON CONFLICT (asset_id, component_id) DO NOTHING
        """,
        asset_id,
        component_id,
    )


__all__.extend(["upsert_asset", "upsert_component", "link_asset_component"])

async def set_asset_exposure(asset_id: str, external: bool):
    try:
        await postgres.execute("UPDATE assets SET external_exposure=$1 WHERE id=$2", external, asset_id)
    except Exception:
        pass

__all__.append("set_asset_exposure")

# --- Enrichment & Finding State Helpers ---

async def update_vulnerability_enrichment(cve_id: str, epss_ts: float | None = None, kev_ts: float | None = None):
    sets = []
    args: list[Any] = []  # type: ignore
    if epss_ts is not None:
        sets.append(f"enrichment_epss_ts=$%d" % (len(args) + 1))
        args.append(epss_ts)
    if kev_ts is not None:
        sets.append(f"enrichment_kev_ts=$%d" % (len(args) + 1))
        args.append(kev_ts)
    if not sets:
        return
    args.append(cve_id)
    sql = f"UPDATE vulnerabilities SET {', '.join(sets)} WHERE cve_id=$%d" % (len(args))
    await postgres.execute(sql, *args)


async def get_finding(fid: str) -> Optional[Dict[str, Any]]:
    rows = await postgres.fetch("SELECT * FROM findings WHERE id=$1", fid)
    return _row_to_dict(rows[0]) if rows else None


async def update_finding_state(fid: str, new_state: str, event_ts: float, reason: str | None = None):
    # Retrieve existing state
    f = await get_finding(fid)
    if not f:
        raise RuntimeError("finding_not_found")
    old_state = f.get("state")
    if old_state == new_state:
        return False
    await postgres.execute("UPDATE findings SET state=$1, last_seen=$2 WHERE id=$3", new_state, event_ts, fid)
    # Insert finding event
    await postgres.execute(
        """
        INSERT INTO finding_events (id, finding_id, event_ts, event_type, payload)
        VALUES ($1,$2,$3,$4,$5)
        """,
        f"fevt-{fid}-{int(event_ts)}",
        fid,
        event_ts,
        "state_change",
        json.dumps({"from": old_state, "to": new_state, "reason": reason}),
    )
    return True


async def vuln_stats() -> Dict[str, Any]:
    # Aggregations: counts by severity, exploit flag, KEV
    sev_rows = await postgres.fetch("SELECT severity, count(*) FROM vulnerabilities GROUP BY severity")
    exploit_rows = await postgres.fetch("SELECT exploit_available, count(*) FROM vulnerabilities GROUP BY exploit_available")
    kev_rows = await postgres.fetch("SELECT kev_listed, count(*) FROM vulnerabilities GROUP BY kev_listed")
    return {
        "severity": { (r[0] or "UNKNOWN"): r[1] for r in sev_rows },
        "exploit_available": { str(r[0]): r[1] for r in exploit_rows },
        "kev_listed": { str(r[0]): r[1] for r in kev_rows },
    }


async def upsert_feed_state(feed_name: str, etag: str | None, status: str, error: str | None = None):
    await postgres.execute(
        """
        INSERT INTO feed_state (feed_name, etag, last_fetch_ts, last_status, last_error)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (feed_name) DO UPDATE SET
          etag=EXCLUDED.etag,
          last_fetch_ts=EXCLUDED.last_fetch_ts,
          last_status=EXCLUDED.last_status,
          last_error=EXCLUDED.last_error
        """,
        feed_name,
        etag,
        float(time.time()),
        status,
        error,
    )

async def get_feed_state(feed_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current persisted feed state (etag, last status, timestamps).

    Returns dict or None if no record. Best-effort: propagates DB errors to caller.
    """
    rows = await postgres.fetch("SELECT * FROM feed_state WHERE feed_name=$1", feed_name)
    return _row_to_dict(rows[0]) if rows else None

__all__.extend([
    "update_vulnerability_enrichment",
    "get_finding",
    "update_finding_state",
    "vuln_stats",
    "upsert_feed_state",
    "get_feed_state",
])

# --- Component -> Vulnerability Matching & Finding Creation ---

async def match_components_to_vulnerabilities(limit: int = 500) -> int:
    """Best‑effort creation/update of findings by matching SBOM components to vulnerabilities.

    Heuristics:
      1. Exact match on normalized component name to vulnerability raw_json product names (if stored) OR alias hit.
      2. Fallback: match CVE ID substring appears in component purl (rare but sometimes embedded in patched forks) – low confidence, skipped for now.
      3. Version gating (simplistic): if vulnerability raw_json includes version ranges (start/end) attempt numeric compare; otherwise accept.

    Current schema lacks a dedicated affected_products table; we therefore inspect vulnerabilities.raw_json JSON for common keys:
      - configurations / nodes / cpeMatch (NVD style) capturing cpe23Uri strings; we extract the product segment.

    Finding ID strategy: f"finding-{asset_id}-{cve_id}-{component_id}" hashed/truncated to ensure idempotent upsert.

    Returns number of findings inserted/updated.

    Compliance Mapping (conceptual, NOT authoritative text):
      - ISO 27001 Annex A (e.g., A.12.6 Vulnerability management) – demonstrates identification of vulnerabilities in assets.
      - NIST CSF (ID.AM, PR.IP, DE.CM, RS.MI) – supports identification and mitigation workflow.
      - SOC 2 (Security, Change Management) – evidence of systematic vulnerability identification across components.
    """
    # Fetch candidate joined rows: components linked to assets; vulnerabilities with potential name overlap
    # We push filtering to SQL where practical for efficiency, but some JSON extraction may require client logic.
    # Step 1: pull components + assets
    comp_rows = await postgres.fetch(
        """
        SELECT ac.asset_id, c.id as component_id, c.name as component_name, c.version as component_version, c.purl
        FROM asset_components ac
        JOIN sbom_components c ON ac.component_id = c.id
        LIMIT $1
        """,
        limit,
    )
    if not comp_rows:
        return 0
    # Step 2: pull vulnerabilities (limit to reasonable window)
    vuln_rows = await postgres.fetch(
        """
        SELECT v.* FROM vulnerabilities v
        ORDER BY v.modified_ts DESC NULLS LAST
        LIMIT $1
        """,
        max(1000, limit * 4),
    )
    if not vuln_rows:
        return 0
    # Build index of vulnerability candidate product names
    vulns_index: list[tuple[dict, set[str]]] = []
    # Attempt OSV alias fetch (best-effort): gather component (name, ecosystem) pairs
    alias_map: dict[str, list[str]] = {}
    if fetch_osv_aliases:
        try:
            comp_name_pairs = []  # ecosystem currently not stored on asset_components join fetch; attempt from sbom_components purl/ecosystem
            for cr in comp_rows:
                cd = _row_to_dict(cr)
                comp_name = cd.get("component_name")
                if comp_name:
                    comp_name_pairs.append((comp_name, "PyPI"))
            if comp_name_pairs:
                fetched = await fetch_osv_aliases(list(set(comp_name_pairs)))
                for k, v in fetched.items():
                    alias_map[k] = v
                # Record simple hit/miss metrics per component queried
                if VULN_OSV_ALIAS_HITS_TOTAL:
                    for pair in set(comp_name_pairs):
                        if pair in fetched:
                            VULN_OSV_ALIAS_HITS_TOTAL.labels("hit").inc()
                        else:
                            VULN_OSV_ALIAS_HITS_TOTAL.labels("miss").inc()
        except Exception:
            alias_map = {}
    for vr in vuln_rows:
        vd = _row_to_dict(vr)
        raw = vd.get("raw_json") or {}
        names: set[str] = set()
        try:
            # NVD style: configurations.nodes[].cpeMatch[].cpe23Uri -> cpe:2.3:a:vendor:product:version:...
            for node in (raw.get("configurations") or {}).get("nodes", []):
                for cm in node.get("cpeMatch", []):
                    cpe = cm.get("cpe23Uri")
                    if isinstance(cpe, str):
                        parts = cpe.split(":")
                        if len(parts) >= 5:
                            names.add(parts[4])  # product segment
        except Exception:
            pass
        # Add alias tokens (including OSV expanded)
        try:
            alias_tokens = set((vd.get("aliases") or []) or [])
            # If vulnerability cve_id present in alias_map keys (OSV), merge
            cve_id = vd.get("cve_id")
            if cve_id and cve_id in alias_map:
                alias_tokens.update(alias_map[cve_id])
            for a in alias_tokens:
                if isinstance(a, str):
                    names.add(a.lower())
        except Exception:
            pass
        # Also retain raw cpeMatch arrays for version applicability decisions later
        cpe_matches: list[dict] = []
        try:
            for node in (raw.get("configurations") or {}).get("nodes", []):
                for cm in node.get("cpeMatch", []):
                    if isinstance(cm, dict):
                        cpe_matches.append(cm)
        except Exception:
            pass
        vulns_index.append((vd, {n for n in names if n}, cpe_matches))
    now_ts = time.time()
    inserted = 0
    # Runtime param toggles
    try:
        params_cache = runtime_params()
        debug_versions = bool(params_cache.get("vuln", {}).get("match", {}).get("debug_version", False) or params_cache.get("vuln.match.debug_version", False))
    except Exception:
        debug_versions = False
    # Batch cap param (supports both nested map and flat key forms)
    try:
        max_batch = params_cache.get("vuln", {}).get("match", {}).get("max_batch")
        if max_batch is None:
            max_batch = params_cache.get("vuln.match.max_batch")
        if max_batch is not None:
            try:
                max_batch = int(max_batch)
            except Exception:
                max_batch = None
    except Exception:
        max_batch = None
    effective_rows = comp_rows
    if max_batch is not None and max_batch >= 0 and len(effective_rows) > max_batch:
        effective_rows = effective_rows[:max_batch]
        if VULN_MATCH_BATCH_TRUNCATED_TOTAL:
            try:
                VULN_MATCH_BATCH_TRUNCATED_TOTAL.inc()
            except Exception:
                pass
        if debug_versions:
            log.debug("batch_truncated original=%d truncated=%d max_batch=%d", len(comp_rows), len(effective_rows), max_batch)
    for comp in effective_rows:
        comp_d = _row_to_dict(comp)
        cname = (comp_d.get("component_name") or "").lower()
        if not cname:
            continue
        cversion = comp_d.get("component_version") or None
        for vrec, name_set, cpe_matches in vulns_index:
            if not name_set:
                # fallback to simple name equality on vulnerability cve_id alias tokens
                pass
            match = False
            if cname in name_set:
                match = True
            # Additional heuristic: direct alias match (if component name equals CVE id alias lowercase)
            if not match and cname in {(vrec.get("cve_id") or "").lower()}:
                match = True
            if not match:
                continue
            # Version applicability: if vulnerability supplies cpeMatches with version ranges, ensure component version falls within at least one.
            if cpe_matches:
                try:
                    applies = any_cpe_match_applies(cpe_matches, cversion)
                except Exception as e:  # noqa: BLE001
                    if debug_versions:
                        log.debug("version_applicability_error component=%s version=%s cve=%s error=%s", cname, cversion, vrec.get("cve_id"), getattr(e, 'message', repr(e)))
                    applies = True  # fail-open
                if not applies:
                    VULN_VERSION_FILTERED_TOTAL.labels("not_in_range").inc()
                    if debug_versions:
                        # Summarize first CPE clause for context
                        snippet = None
                        try:
                            first = next((cm for cm in cpe_matches if isinstance(cm, dict)), None)
                            if first:
                                snippet = {
                                    k: first.get(k) for k in [
                                        "vulnerable","cpe23Uri","versionStartIncluding","versionStartExcluding","versionEndIncluding","versionEndExcluding"
                                    ] if k in first
                                }
                        except Exception:
                            pass
                        log.debug("version_filtered component=%s version=%s cve=%s snippet=%s", cname, cversion, vrec.get("cve_id"), snippet)
                    continue
            elif cversion is None:
                # Vulnerability has no explicit cpeMatches; if component has no version, we still allow; else accept universally
                pass
            fid_raw = f"finding-{comp_d.get('asset_id')}-{vrec.get('cve_id')}-{comp_d.get('component_id')}"
            fid = f"f-{hashlib.sha256(fid_raw.encode()).hexdigest()[:24]}"
            # Compute simple risk placeholders (risk model expansion later)
            # For now severity -> risk score mapping (0..1) weight with exploit flags
            sev = (vrec.get("severity") or "UNKNOWN").upper()
            sev_map = {"CRITICAL": 0.95, "HIGH": 0.75, "MEDIUM": 0.5, "LOW": 0.25}
            base = sev_map.get(sev, 0.1)
            if vrec.get("exploit_available"):
                base = min(1.0, base + 0.1)
            risk_sev = (
                "CRITICAL" if base >= 0.85 else
                "HIGH" if base >= 0.65 else
                "MEDIUM" if base >= 0.4 else
                "LOW" if base > 0 else
                "NONE"
            )
            rec = {
                "id": fid,
                "cve_id": vrec.get("cve_id"),
                "asset_id": comp_d.get("asset_id"),
                "component_id": comp_d.get("component_id"),
                "first_seen": now_ts,
                "last_seen": now_ts,
                "state": "open",
                "detection_source": "sbom_match",
                "risk_score": base,
                "risk_severity": risk_sev,
                "asset_metadata": json.dumps({"criticality": (comp_d.get("criticality") or 0.5)}),
                "sla_due_ts": None,
                "risk_factors": {
                    "severity_component": sev_map.get(sev, 0.1),
                    "exploit_component": 1.0 if vrec.get("exploit_available") else 0.0,
                },
            }
            # SLA due timestamp assignment (only if new finding) based on flat runtime params keys vuln.sla.days.*
            try:
                sev_key = risk_sev.lower()
                param_key = f"vuln.sla.days.{sev_key}"
                days_val = runtime_params.get_param(param_key)
                if days_val is not None:
                    try:
                        days_f = float(days_val)
                        if days_f >= 0:
                            rec["sla_due_ts"] = now_ts + days_f * 86400.0
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                # Idempotency: skip counting if finding already exists
                existing = await postgres.fetch("SELECT id FROM findings WHERE id=$1", fid)
                await upsert_finding(rec)
                if not existing:
                    inserted += 1
            except Exception:
                continue
    return inserted

__all__.append("match_components_to_vulnerabilities")
