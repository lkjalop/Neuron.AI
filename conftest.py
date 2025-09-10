"""Test configuration: ensure src directory is on sys.path for imports.

This avoids ModuleNotFoundError for 'core', 'iam', etc., when running tests
without installing the package. Keeps developer loop lightweight.
"""
import sys
from pathlib import Path
import pytest

@pytest.fixture
async def started_pipeline():
    """Provide a started Pipeline for tests needing live async loop.

    Ensures proper shutdown to avoid cross-test interference or lingering tasks.
    """
    from core.pipeline import Pipeline
    p = Pipeline(["tenant_fx"])
    await p.start()
    try:
        yield p
    finally:
        await p.stop()
_ROOT = Path(__file__).resolve().parent
src = _ROOT / 'src'
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
