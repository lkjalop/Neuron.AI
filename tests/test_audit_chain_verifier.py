import subprocess, sys, pathlib, json, time
from config import runtime_params

def test_audit_chain_verifier_runs(tmp_path):
    # Trigger a few param changes to ensure log has entries
    runtime_params.update_param('baseline.window_size', 55, reason='test_audit_chain_verifier')
    runtime_params.update_param('baseline.stddev_threshold', 2.5, reason='test_audit_chain_verifier')
    # Invoke the script in a subprocess (uses current interpreter)
    script = pathlib.Path('scripts/verify_audit_chain.py')
    assert script.exists(), 'Verifier script missing'
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        print('STDOUT:', proc.stdout)
        print('STDERR:', proc.stderr)
    assert proc.returncode == 0, 'Audit chain verifier reported failure'
    assert 'Audit chain verified' in proc.stdout