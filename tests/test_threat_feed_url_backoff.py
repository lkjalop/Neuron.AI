import time

import pytest


def test_url_feed_backoff_error(monkeypatch):
    # Use the feed manager to register a temporary URL feed pointing to an invalid URL to force errors
    from core.threat_feeds import manager as tfm  # type: ignore
    from core import metrics  # type: ignore

    mgr = getattr(tfm, 'threat_feed_manager', None)
    if mgr is None:
        pytest.skip('Threat feed manager not available in this build')

    # Register a temporary feed which will fail
    feed = tfm.ThreatFeed(
        name='test_bad_url',
        fetch_fn=lambda: (_ for _ in ()).throw(RuntimeError('boom')),
        interval_s=0.01,
    )
    mgr.register(feed)

    # Run a few iterations of the loop body manually if available
    # Fallback: call fetch_once directly to simulate a cycle
    for _ in range(5):
        try:
            feed.fetch_once()
        except Exception:
            pass
        time.sleep(0.005)

    # Assert metrics updated (errors/backoff)
    if hasattr(metrics, 'THREAT_FEED_STATUS_TOTAL'):
        err = metrics.THREAT_FEED_STATUS_TOTAL.labels(feed='test_bad_url', status='error')._value.get()
        assert err >= 1
    else:
        pytest.skip('Threat feed metrics not available')

    # Cleanup
    try:
        # best-effort cleanup to avoid side effects on subsequent tests
        mgr._feeds.pop('test_bad_url', None)  # type: ignore[attr-defined]
    except Exception:
        pass
