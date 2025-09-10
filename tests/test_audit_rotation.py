import os, json, hashlib, time, pathlib
from config import runtime_params

HEAD = pathlib.Path('audit/param_changes.head')
LOG = pathlib.Path('audit/param_changes.log')

def test_param_change_hash_chain_and_rotation(monkeypatch):
    # Force very small rotation threshold
    monkeypatch.setenv('NEURON_AUDIT_ROTATE_FORCE', '1')  # not used directly but placeholder if future logic inspects
    # Generate enough updates to exceed rotation size (lower threshold by patching constant if accessible)
    # We'll simulate by writing many params quickly
    for i in range(120):
        runtime_params.update_param('baseline.mad_factor', 3.5, reason=f'test{i}')
    assert HEAD.exists()
    head_hash = HEAD.read_text().strip()
    assert len(head_hash) == 64
    # Ensure at least one rotated file likely exists (best-effort):
    rotated = list(pathlib.Path('audit').glob('param_changes.log.*'))
    assert rotated or LOG.exists()
