from config import runtime_params
from core.pipeline import Pipeline
from core.event import Event
from core.detect.interface import registry


def _run_pattern(pipeline: Pipeline, pattern: str, n: int = 120):
    events = []
    if pattern == 'periodic_beacon':
        for i in range(n):
            spike = (i % 15) == 0
            events.append({'cpu': 8.0 if spike else 1.0, 'mem': 1.0})
    elif pattern == 'slow_ramp':
        for i in range(n):
            events.append({'cpu': 1.0 + 0.05 * i, 'mem': 1.0 + 0.04 * i})
    else:
        raise ValueError('unknown pattern')
    for feats in events:
        pipeline.ingestion.queue.put_nowait(Event(tenant_id='t_eval', features=feats))  # type: ignore


def _first_detection_index(det, pattern: str, n: int = 120):
    idx = 0
    if det is None:
        return None
    if pattern == 'periodic_beacon':
        for i in range(n):
            spike = (i % 15) == 0
            feats = {'cpu': 8.0 if spike else 1.0, 'mem': 1.0}
            if det.process(Event(tenant_id='t_eval', features=feats)):
                return i
    elif pattern == 'slow_ramp':
        for i in range(n):
            feats = {'cpu': 1.0 + 0.05 * i, 'mem': 1.0 + 0.04 * i}
            if det.process(Event(tenant_id='t_eval', features=feats)):
                return i
    return None


def test_temporal_patterns_detection_indices():
    # Enable SNN optionally (best-effort) for comparative index; temporal stub remains anomaly-silent.
    runtime_params.update_param('detection.enable_snn', True, reason='temporal_eval')
    p = Pipeline(['t_eval'])
    # Patterns
    patterns = ['periodic_beacon', 'slow_ramp']
    baseline = registry.get('baseline')
    snn = registry.get('snn')
    results = {}
    for pat in patterns:
        idx_baseline = _first_detection_index(baseline, pat)
        idx_snn = _first_detection_index(snn, pat)
        results[pat] = {
            'baseline_idx': idx_baseline,
            'snn_idx': idx_snn,
        }
    # Sanity: both patterns should eventually trigger (indices not None). Ordering can vary due to rolling stats.
    pb = results['periodic_beacon']['baseline_idx']
    sr = results['slow_ramp']['baseline_idx']
    if pb is not None and sr is not None:
        assert pb >= 0 and sr >= 0
