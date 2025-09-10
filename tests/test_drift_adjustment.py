import pytest, time
from fastapi.testclient import TestClient
from core.main import app, _maybe_adjust_temporal_weight

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'adminkey')
    return TestClient(app)

@pytest.mark.asyncio
async def test_drift_adjustment_cooldown(monkeypatch):
    # Reset internal state
    import core.main as cm
    cm._RETRIEVAL_LAST_ADJUST_TS = None
    from core import metrics as m
    before = m.FUSION_TEMPORAL_WEIGHT.labels(tenant='global')._value.get() if hasattr(m.FUSION_TEMPORAL_WEIGHT, '_metrics') else None
    _maybe_adjust_temporal_weight(added=10, updated=0)  # triggers
    first_ts = cm._RETRIEVAL_LAST_ADJUST_TS
    assert first_ts is not None
    # Immediate second call should cooldown skip (timestamp unchanged)
    _maybe_adjust_temporal_weight(added=10, updated=0)
    assert cm._RETRIEVAL_LAST_ADJUST_TS == first_ts

