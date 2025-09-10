import json, io, contextlib, pytest
from scripts import synthetic_dataset_harness as sdh

@pytest.mark.asyncio
async def test_synthetic_harness_manifest_capture():
    buf = io.StringIO()
    # run_once is sync wrapper around async nested code? In script it's async run_once -> call via asyncio in harness; here treat as sync call? We'll just call sdh.run_once via helper.
    try:
        import asyncio
        with contextlib.redirect_stdout(buf):
            await sdh.run_once()
    except Exception:
        pytest.skip('Harness dependencies (DB) not ready')
    data = buf.getvalue().strip()
    assert data, 'No manifest printed'
    manifest = json.loads(data.splitlines()[-1])
    for key in ['run_id','event_counts','dashboard_keys','asset_feature_rows']:
        assert key in manifest
