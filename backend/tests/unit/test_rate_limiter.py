"""Unit tests for Token Bucket Rate Limiter."""

import time
import pytest
from app.core.rate_limiter import TokenBucket, RateLimiter


def test_token_bucket_allows_burst_within_capacity():
    bucket = TokenBucket(capacity=3, refill_rate=1.0)
    
    # 3 rapid calls should all succeed
    assert bucket.consume()[0] is True
    assert bucket.consume()[0] is True
    assert bucket.consume()[0] is True
    
    # 4th call should be rejected
    allowed, remaining, retry_after = bucket.consume()
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(capacity=2, refill_rate=10.0)  # 10 tokens per second
    
    # Drain bucket
    bucket.consume()
    bucket.consume()
    assert bucket.consume()[0] is False
    
    # Wait 0.15s (should add ~1.5 tokens)
    time.sleep(0.15)
    allowed, remaining, _ = bucket.consume()
    assert allowed is True


def test_rate_limiter_isolates_client_keys():
    limiter = RateLimiter(capacity=2, refill_rate=0.5)
    
    # Client A drains bucket
    assert limiter.check("client_A")[0] is True
    assert limiter.check("client_A")[0] is True
    assert limiter.check("client_A")[0] is False
    
    # Client B should still have full quota
    assert limiter.check("client_B")[0] is True
    assert limiter.check("client_B")[0] is True
