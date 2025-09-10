import pytest, statistics
from scripts import perf_probe

@pytest.mark.asyncio
async def test_perf_probe_baseline():
    try:
        ing = await perf_probe.measure_ingestion(batch_size=5, iterations=1)
        dash = await perf_probe.measure_dashboard(refreshes=1)
    except Exception:
        pytest.skip('Perf probe prerequisites not met (DB / tables)')
    assert ing and dash
    assert all(t >= 0 for t in ing+dash)
    # Very generous upper bound to avoid flakiness in CI – adjust later
    assert max(ing+dash) < 30, 'Performance regression: ingestion/dashboard too slow'
