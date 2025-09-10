import asyncio, json
import types
from pathlib import Path

from observability import tracing
from reports.unified_pipeline import build_report_bundle
from governance.weight_governor import run_once_for_test


async def _gen_report():
    return await build_report_bundle(include_html=False, include_diff=False)


def test_report_tracing_and_governor_span(monkeypatch):
    # Ensure tracing buffer clear
    tracing.clear()
    # Monkeypatch governor enable param
    from config import runtime_params
    monkeypatch.setattr(runtime_params, 'get_param', lambda k: 1 if k == 'governance.weight.enable' else 0)
    # Run governor single pass (will produce at least one span even if metrics empty)
    run_once_for_test()
    # Run report bundle
    asyncio.run(_gen_report())
    spans = tracing.get_spans(100)
    names = {s['name'] for s in spans}
    assert 'governor.evaluate' in names
    assert 'report.bundle' in names
    # report.bundle should have duration_ms field
    rep = [s for s in spans if s['name'] == 'report.bundle']
    assert rep and rep[0]['duration_ms'] >= 0
