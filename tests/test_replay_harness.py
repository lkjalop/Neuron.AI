import os, json
from pathlib import Path

from core.main import build_app
from scripts.replay_harness import load_events, run_replay, analyze


def test_replay_harness_basic(tmp_path):
    # Use existing events.jsonl at repo root if present, else synthesize small set
    events_path = Path('events.jsonl')
    if not events_path.exists():
        sample = [
            {"event_id": f"e{i}", "tenant_id": "tenantA", "category": "catA", "value": i} for i in range(30)
        ]
        events_path.write_text("\n".join(json.dumps(e) for e in sample), encoding='utf-8')
    events = load_events(str(events_path), max_events=50)
    assert events, 'events should load'
    app = build_app()
    results = run_replay(app, events, iterations=2)
    assert 'composite_sequences' in results
    assert len(results['composite_sequences']) == 2
    analysis = analyze(results, max_composite_drift=0.5, require_retrieval_stability=False)
    # Basic shape assertions
    assert 'composite_drift' in analysis
    assert isinstance(analysis['composite_drift'], float)
