"""ATT&CK mapping enrichment helpers.

Responsible for:
 - Ingesting lightweight reference data for techniques and software.
 - Linking vulnerabilities to software (manual or feed-based association placeholder).
 - Resolving transitive mapping: CVE -> Software -> Techniques.

Functions are best-effort and tolerate missing tables.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional

from storage import postgres  # type: ignore

async def upsert_attack_technique(tech: Dict[str, Any]):
    await postgres.execute(
        """
        INSERT INTO attack_techniques (technique_id, name, tactic, description)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (technique_id) DO UPDATE SET
          name=EXCLUDED.name,
          tactic=EXCLUDED.tactic,
          description=EXCLUDED.description
        """,
        tech.get("technique_id"), tech.get("name"), tech.get("tactic"), tech.get("description")
    )

async def upsert_attack_software(soft: Dict[str, Any]):
    await postgres.execute(
        """
        INSERT INTO attack_software (software_id, name, type, description)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (software_id) DO UPDATE SET
          name=EXCLUDED.name,
          type=EXCLUDED.type,
          description=EXCLUDED.description
        """,
        soft.get("software_id"), soft.get("name"), soft.get("type"), soft.get("description")
    )

async def link_vuln_software(cve_id: str, software_id: str):
    await postgres.execute(
        """
        INSERT INTO vuln_software_map (cve_id, software_id)
        VALUES ($1,$2)
        ON CONFLICT (cve_id, software_id) DO NOTHING
        """,
        cve_id, software_id
    )

async def link_software_technique(software_id: str, technique_id: str):
    await postgres.execute(
        """
        INSERT INTO software_technique_map (software_id, technique_id)
        VALUES ($1,$2)
        ON CONFLICT (software_id, technique_id) DO NOTHING
        """,
        software_id, technique_id
    )

async def vulnerability_techniques(cve_id: str) -> List[Dict[str, Any]]:
    rows = await postgres.fetch(
        """
        SELECT t.technique_id, t.name, t.tactic
        FROM vuln_software_map vsm
        JOIN software_technique_map stm ON vsm.software_id = stm.software_id
        JOIN attack_techniques t ON stm.technique_id = t.technique_id
        WHERE vsm.cve_id=$1
        """,
        cve_id
    )
    return [dict(r) for r in rows]

async def vulnerability_attack_context(cve_id: str) -> Dict[str, Any]:
    rows = await postgres.fetch(
        """
        SELECT s.software_id, s.name as software_name, s.type as software_type,
               t.technique_id, t.name as technique_name, t.tactic
        FROM vuln_software_map vsm
        JOIN attack_software s ON vsm.software_id = s.software_id
        LEFT JOIN software_technique_map stm ON s.software_id = stm.software_id
        LEFT JOIN attack_techniques t ON stm.technique_id = t.technique_id
        WHERE vsm.cve_id=$1
        """,
        cve_id
    )
    context: Dict[str, Any] = {"software": {}, "techniques": {}}
    for r in rows:
        sd = context["software"].setdefault(r["software_id"], {"name": r["software_name"], "type": r["software_type"]})
        if r.get("technique_id"):
            context["techniques"].setdefault(r["technique_id"], {"name": r["technique_name"], "tactic": r["tactic"]})
    return context

__all__ = [
    "upsert_attack_technique",
    "upsert_attack_software",
    "link_vuln_software",
    "link_software_technique",
    "vulnerability_techniques",
    "vulnerability_attack_context",
]
