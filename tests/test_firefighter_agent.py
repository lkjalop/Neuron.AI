from core.failover.firefighter import DisableCycleWindow
import time

def test_no_incident_initial():
    win = DisableCycleWindow(window_sec=60, threshold=3, suppress_cooldown_sec=5)
    assert win.evaluate() is None


def test_incident_trigger_and_suppression():
    win = DisableCycleWindow(window_sec=60, threshold=3, suppress_cooldown_sec=5)
    now = time.time()
    for i in range(3):
        win.add_disable(now + i * 1)
    incident = win.evaluate()
    assert incident is not None
    # Immediate re-evaluation suppressed
    assert win.evaluate() is None
    # After cooldown, new cycle triggers again
    time.sleep(5.2)
    win.add_disable(time.time())
    win.add_disable(time.time())
    win.add_disable(time.time())
    incident2 = win.evaluate()
    assert incident2 is not None
    assert incident2["cycles"] >= 3
