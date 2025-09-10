"""Auto-link knowledge articles to vulnerabilities, controls, attack patterns.

Patterns:
  CVE IDs: CVE-YYYY-NNNN -> link RELATES_TO to vulnerability node id 'vuln:<cve>' if exists
  ATT&CK: T\d{4,5} -> link RELATES_TO to attack pattern node id 'attk:<tech>' (create stub if missing)
  Controls: CIS-\d+(?:\.\d+)* or NIST-[A-Z]+-[A-Z]+-\d+(?:\.\d+)* -> link RELATES_TO to ctrl:<id>

Usage:
  python -m scripts.auto_link_knowledge --limit 100
"""
from __future__ import annotations

import re, asyncio, argparse, time
from storage.graph_store import get_node, upsert_node, upsert_edge
from storage import postgres

CVE_RE = re.compile(r"CVE-20\d{2}-\d{4,7}")
ATTACK_RE = re.compile(r"T\d{4,5}")
CTRL_RE = re.compile(r"(?:CIS-\d+(?:\.\d+)*|NIST-[A-Z]+-[A-Z]+-\d+(?:\.\d+)*)")


async def fetch_articles(limit: int):
    rows = await postgres.fetch(
        "SELECT id, properties->>'body' AS body FROM graph_nodes WHERE node_type='KNOWLEDGE_ARTICLE' LIMIT $1",
        limit,
    )
    return [(r[0], r[1] or "") for r in rows]


async def process_article(article_id: str, body: str):
    seen_edges = set()
    for cve in set(CVE_RE.findall(body)):
        vid = f"vuln:{cve}" if not cve.startswith("vuln:") else cve
        # Create stub vulnerability node if absent (placeholder until enrichment)
        if not await get_node(vid):
            await upsert_node(vid, "VULNERABILITY", {"cve_id": cve})
        await upsert_edge(article_id, vid, "RELATES_TO", {"pattern": "cve"})
        seen_edges.add((article_id, vid))
    for tech in set(ATTACK_RE.findall(body)):
        tid = f"attk:{tech}" if not tech.startswith("attk:") else tech
        if not await get_node(tid):
            await upsert_node(tid, "ATTACK_PATTERN", {"technique": tech})
        await upsert_edge(article_id, tid, "RELATES_TO", {"pattern": "attack"})
        seen_edges.add((article_id, tid))
    for ctrl in set(CTRL_RE.findall(body)):
        cid = f"ctrl:{ctrl}" if not ctrl.startswith("ctrl:") else ctrl
        if not await get_node(cid):
            await upsert_node(cid, "CONTROL", {"control_id": ctrl})
        await upsert_edge(article_id, cid, "RELATES_TO", {"pattern": "control"})
        seen_edges.add((article_id, cid))
    return len(seen_edges)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()
    arts = await fetch_articles(args.limit)
    total_links = 0
    for aid, body in arts:
        total_links += await process_article(aid, body)
    print(f"Linked edges created/ensured: {total_links}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
