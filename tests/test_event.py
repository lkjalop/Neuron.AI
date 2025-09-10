from core.event import Event, validate_event


def test_validate_event_basic():
    # Use factory compatibility via dict_to_event semantics; direct Event requires required core fields.
    ev = Event.create("generic", tenant_id="t1", source="sim", features={"x": 1.0}, labels={})
    validate_event(ev)  # should not raise
