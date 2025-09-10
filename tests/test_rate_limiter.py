import time
from core.ratelimit import TokenBucket


def test_rate_limiter_burst_and_refill():
    bucket = TokenBucket(capacity=3, fill_rate=1.0)
    assert sum(bucket.consume() for _ in range(3)) == 3
    assert not bucket.consume()  # exhausted
    time.sleep(1.1)
    assert bucket.consume()  # refilled at least one token
