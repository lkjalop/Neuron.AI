"""Generate vulnerability report (JSON + optional HTML) using reports.generator."""
import asyncio
import json
from storage import vuln_store
try:
    from reports.generator import render_executive_summary
except ImportError:
    render_executive_summary = None

async def main(html: bool = False, limit: int = 100):
    vulns = await vuln_store.list_vulnerabilities(limit=limit)
    findings = await vuln_store.list_findings(limit=limit)
    report = {
        "vulnerabilities": vulns,
        "findings": findings,
    }
    with open("vuln_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Wrote vuln_report.json")
    if html and render_executive_summary:
        html_out = await render_executive_summary()
        with open("vuln_report.html", "w", encoding="utf-8") as f:
            f.write(html_out)
        print("Wrote vuln_report.html")

if __name__ == "__main__":
    asyncio.run(main(html=True))
