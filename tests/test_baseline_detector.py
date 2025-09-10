from core.detect.baseline import BaselineDetector
from core.event import Event


def test_baseline_detector_anomaly_path():
    det = BaselineDetector(window=10, stddev_threshold=1.0, warmup_min=5)  # lower warmup to trigger earlier
    # feed consistent values (establish mean/std)
    for _ in range(6):
        det.process(Event.create("generic", tenant_id="t1", source="sim", features={"cpu": 1.0}, labels={}))
    # outlier
    anomalies = det.process(Event.create("generic", tenant_id="t1", source="sim", features={"cpu": 10.0}, labels={}))
    assert anomalies, "Expected anomaly for outlier"
