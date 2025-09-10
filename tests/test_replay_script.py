from __future__ import annotations
import json, pathlib, os, subprocess, sys

import pytest


def test_replay_script_basic(tmp_path: pathlib.Path):
    # Create small event dataset
    events_path = tmp_path / "events.jsonl"
    data = [
        {"event_type": "e", "severity": 10.0, "features": {"f0": 1.0, "f1": 2.0}, "tenant_id": "t"},
        {"event_type": "e", "severity": 30.0, "features": {"f0": 5.0, "f1": 10.0}, "tenant_id": "t"},
    ]
    with events_path.open('w', encoding='utf-8') as f:
        for row in data:
            f.write(json.dumps(row) + "\n")
    summary_path = tmp_path / "summary.json"
    cmd = [sys.executable, str(pathlib.Path('scripts/replay_events.py')), '--input', str(events_path), '--summary', str(summary_path)]
    env = os.environ.copy()
    # Set PYTHONPATH to include src directory
    env['PYTHONPATH'] = str(pathlib.Path('src').absolute())
    # Keep detectors minimal for test speed
    env.pop('ENABLE_SNN', None)
    env.pop('EXPERIMENTAL_ISOFOREST', None)
    subprocess.check_call(cmd, env=env)
    assert summary_path.exists(), "Summary file not created"
    summary = json.loads(summary_path.read_text())
    assert summary['total_events'] == 2
    assert 'total_anomalies' in summary
