import pytest, time
from dashboard.aggregator import refresh_dashboard
from reports.generator import render_executive_summary
from storage import postgres


@pytest.mark.asyncio
async def test_dashboard_and_report_flow():
    # Create minimal vulnerability + finding data if tables empty
    try:
        vuln_rows = await postgres.fetch('SELECT id FROM vulnerabilities LIMIT 1')
    except Exception:
        pytest.skip('vulnerabilities table not available')
    if not vuln_rows:
        # Insert synthetic vulnerability and finding directly
        now = time.time()
        await postgres.execute("INSERT INTO vulnerabilities (id, severity, exploit_available) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING","vuln-test-1","HIGH",True)
        await postgres.execute("INSERT INTO findings (id, cve_id, asset_id, component_id, first_seen, last_seen, state, detection_source, risk_score, risk_severity, asset_metadata, sla_due_ts, risk_factors, treatment_state, accepted_risk, remediation_target_ts) VALUES ($1,$2,$3,$4,$5,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) ON CONFLICT DO NOTHING", 'f-test-1','CVE-2024-1234','asset-a',None, now,'open','qualys.synthetic',0.8,'HIGH','{}',None,'{}',None,None,None)
    snap = await refresh_dashboard()
    assert 'vulnerability_severity' in snap
    html = await render_executive_summary()
    assert '<html' in html.lower() or '<!doctype' in html.lower()
