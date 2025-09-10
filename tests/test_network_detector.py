import time
import pytest
from core.detect.interface import DetectionResult
from detect.network.detector import NetworkFlowDetector
from core.event import Event
from core import metrics

class DummyEvent(Event):
    def __init__(self, tenant_id: str, metadata: dict, labels: dict | None = None):
        self.event_type = "network_flow"
        self.tenant_id = tenant_id
        self.source = "flow"
        self.metadata = metadata
        self.labels = labels or {}
        self.features = {}
        self.timestamp = time.time()

@pytest.mark.parametrize("byte_out,byte_in,expect", [
    (9000, 100, True),  # high ratio
    (10, 4000, True),   # low ratio
    (200, 300, False),  # normal
])
def test_network_detector_byte_ratio(byte_out, byte_in, expect):
    det = NetworkFlowDetector()
    ev = DummyEvent("tenantA", {
        "src_ip": "10.0.0.5",
        "dst_ip": "8.8.8.8",
        "bytes_out": byte_out,
        "bytes_in": byte_in,
        "direction": "out",
        "is_external": True,
        "dst_host": "example.com"
    })
    res = det.process(ev)
    ratio = None
    if res:
        ratio = res[0]["features"].get("net_byte_ratio")
    if expect:
        assert res and res[0]["detector"] == "network", f"expected anomaly; ratio={ratio}"
    else:
        assert res == [], f"unexpected anomaly; ratio={ratio} triggers={res[0].get('triggers') if res else None}"


def test_network_detector_metrics_increment():
    det = NetworkFlowDetector()
    # Trigger anomaly with multiple hosts to add external_host_spike later
    ev = DummyEvent("tenantA", {
        "src_ip": "10.0.0.5",
        "dst_ip": "1.1.1.1",
        "bytes_out": 10000,
        "bytes_in": 10,
        "direction": "out",
        "is_external": True,
        "dst_host": "h1"
    })
    res = det.process(ev)
    assert res, "expected anomaly"
    # Metric presence check (labels may or may not exist depending on global registry state)
    c = metrics.NETWORK_ANOMALIES_TOTAL
    # Access internal _metrics to ensure our tenant label was registered
    label_key_total = (('tenant','tenantA'),('trigger','__total__'))
    # Convert to canonical tuple ordering used by prometheus_client internal storage
    found = False
    for k,v in getattr(c, '_metrics', {}).items():
        # prometheus_client uses a tuple of label values; simpler scan string form
        if '__total__' in str(k) and 'tenantA' in str(k):
            found = True; break
    assert found, "network anomalies metric not incremented for tenantA"
