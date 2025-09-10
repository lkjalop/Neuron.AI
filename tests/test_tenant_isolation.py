from core.detect.baseline import BaselineDetector


def test_tenant_isolation_state():
    det = BaselineDetector(window=10, stddev_threshold=2.0)
    # simulate distinct distributions
    for i in range(30):
        det.process(__import__('types').SimpleNamespace(tenant_id="tenantA", features={"cpu": i}, raw={}, source="sim", labels={}, meta={}, event_id="a", timestamp=0, event_type="evt", version="1.0", trace_id="tA"))  # type: ignore
        det.process(__import__('types').SimpleNamespace(tenant_id="tenantB", features={"cpu": i+100}, raw={}, source="sim", labels={}, meta={}, event_id="b", timestamp=0, event_type="evt", version="1.0", trace_id="tB"))  # type: ignore
    a_mean = det.state["tenantA"]["cpu"].mean
    b_mean = det.state["tenantB"]["cpu"].mean
    assert abs(a_mean - b_mean) > 50
