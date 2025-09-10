import time

from core.threat_feeds.manager import threat_feed_manager
from core import metrics


def test_threat_feed_backoff_error_path(monkeypatch):
    # Ensure global and feed flags enabled by default; rely on defaults
    feed = threat_feed_manager.get("demo")
    assert feed is not None
    # Force error on next fetch
    feed._force_error = True
    # Make it due now
    feed._last_attempt = None
    # Call once to trigger error and set backoff
    feed.fetch_once()
    # After an error, backoff should be > 0
    assert feed._backoff > 0.0
    # Gauge should be set; scrape from registry to ensure label presence
    # We can't easily read Gauge current value; instead iterate samples to ensure label exists
    fam = None
    for collected in metrics.registry().collect():
        if collected.name == "neuron_threat_feed_backoff_seconds":
            fam = collected
            break
    assert fam is not None
    labels_seen = [tuple(s.labels.items()) for s in fam.samples if s.name == "neuron_threat_feed_backoff_seconds"]
    assert any(dict(ls).get("feed") == "demo" for ls in labels_seen)

    # Clear forced error and ensure success resets backoff toward 0
    feed._force_error = False
    # Monkeypatch fetch_fn to return quickly empty list
    monkeypatch.setattr(feed, "fetch_fn", lambda: [])
    # Fast-forward due window
    feed._last_attempt = time.time() - max(feed.interval_s, feed._backoff)
    feed.fetch_once()
    assert feed._backoff == 0.0
