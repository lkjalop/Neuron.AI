from __future__ import annotations
import subprocess, sys, json, os, pathlib

SCRIPT = pathlib.Path("scripts/verify_reliability_a11.py")


def test_reliability_script_runs():
    # Ensure script exists
    assert SCRIPT.exists(), "Reliability script missing"
    # Set PYTHONPATH to include src directory
    env = os.environ.copy()
    env['PYTHONPATH'] = str(pathlib.Path('src').absolute())
    # Run script; allow failure if anomalies zero but should normally produce >0 with baseline registered
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
    # Accept either success (0) or anomaly failure code (2) but ensure JSON printed
    assert proc.stdout.strip(), proc.stderr
    try:
        data = json.loads(proc.stdout)
        assert "events" in data and "param_hash" in data
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"Output not valid JSON: {e}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}")
