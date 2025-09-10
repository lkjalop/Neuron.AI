from snn.encoder_v2 import encode_event, event_seed
from core.event import Event


def test_encode_event_deterministic():
    e = Event.create("unit", severity=5.0, features={"a":1.0, "b":2.0})
    s1 = encode_event(e, neurons=4, buckets=8, base_seed=42)
    s2 = encode_event(e, neurons=4, buckets=8, base_seed=42)
    assert s1 == s2


def test_encode_event_structure():
    e = Event.create("unit", severity=1.0, features={"x":3.14, "y":2.71, "z":0.5})
    spikes = encode_event(e, neurons=5, buckets=10)
    assert len(spikes) == 5
    # At least one spike in first few neurons
    assert any(len(n) > 0 for n in spikes)


def test_event_seed_differs():
    e1 = Event.create("unit", severity=1.0)
    e2 = Event.create("unit", severity=1.0)
    assert event_seed(e1) != event_seed(e2)
