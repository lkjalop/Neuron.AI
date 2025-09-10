from __future__ import annotations
import pytest
import asyncio
from scanner.scanner_agent import run_scan_cycle, _FINDINGS
from core import metrics

@pytest.mark.asyncio
async def test_scanner_loop_creates_findings_and_metrics(monkeypatch):
    # Reset findings
    _FINDINGS.clear()
    # Patch metrics to track calls
    called = {}
    class DummyMetric:
        def labels(self, **kwargs):
            called[tuple(kwargs.items())] = True
            return self
        def set(self, val):
            called['set'] = val
        def inc(self):
            called['inc'] = True
        def observe(self, val):
            called['observe'] = val
    monkeypatch.setattr(metrics, 'VULN_ACTIVE_FINDINGS', DummyMetric())
    monkeypatch.setattr(metrics, 'VULN_SCAN_CYCLES_TOTAL', DummyMetric())
    monkeypatch.setattr(metrics, 'VULN_NORMALIZATION_LATENCY', DummyMetric())
    await run_scan_cycle()
    # At least one finding should be created
    assert len(_FINDINGS) > 0
    # Metrics should be updated
    assert 'set' in called
    assert 'inc' in called
    assert 'observe' in called
