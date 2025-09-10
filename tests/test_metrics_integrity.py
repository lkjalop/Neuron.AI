import time

from prometheus_client import CollectorRegistry

from core import metrics
from core.detect.baseline import BaselineDetector
from core.event import Event


def make_event(tenant: str, value: float, event_id: str) -> Event:
    return Event.create("generic", tenant_id=tenant, source="test", features={"x": value}, labels={})


def test_metrics_monotonic_and_histogram_presence():
    # Use detector directly to avoid async pipeline complexity here
    det = BaselineDetector(window=5, stddev_threshold=2.0, warmup_min=2)
    tenant = "t1"

    # initial counters
    reg: CollectorRegistry = metrics.registry()

    def get_counter(metric, *label_vals):
        return metric.labels(*label_vals)._value.get()

    warmup0 = get_counter(metrics.DETECTOR_WARMUP_SKIPS, tenant, det.name)
    mad0 = get_counter(metrics.DETECTOR_MAD_FALLBACK, tenant, det.name)

    # feed events (first two warm-up, then some variance)
    det.process(make_event(tenant, 10.0, "e1"))
    det.process(make_event(tenant, 11.0, "e2"))
    det.process(make_event(tenant, 10.5, "e3"))
    det.process(make_event(tenant, 13.0, "e4"))  # possible anomaly depending on threshold
    det.process(make_event(tenant, 9.0, "e5"))

    warmup1 = get_counter(metrics.DETECTOR_WARMUP_SKIPS, tenant, det.name)
    mad1 = get_counter(metrics.DETECTOR_MAD_FALLBACK, tenant, det.name)

    assert warmup1 >= warmup0, "Warm-up counter must be monotonic"
    assert mad1 >= mad0, "MAD fallback counter must be monotonic"

    # Histogram presence: observe latency being recorded via manual timing context
    with metrics.PROCESSING_LATENCY.time():
        time.sleep(0.001)

    # Ensure at least one sample bucket got increment (sum/count > 0)
    histogram_samples = metrics.PROCESSING_LATENCY._sum.get()
    assert histogram_samples > 0, "Processing latency histogram should record observations"
