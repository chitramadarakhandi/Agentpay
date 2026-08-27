"""Token Bucket Rate Limiter for sensitive payment endpoints.

Algorithm: Token Bucket
- Each client key (IP or user_id) has a bucket with max_tokens capacity.
- Tokens refill continuously at a rate of (refill_rate) tokens per second.
- Each request consumes 1 token.
- If bucket is empty, request is rejected with HTTP 429 and Retry-After header.

Why Token Bucket?
- Allows short, controlled bursts while enforcing an average rate limit over time.
- Highly memory efficient (O(1) storage per client).
"""

import time
import threading
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException, status


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity: Maximum number of tokens the bucket can hold (burst capacity).
        refill_rate: Number of tokens added to bucket per second.
        """
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens_to_consume: float = 1.0) -> Tuple[bool, int, float]:
        """Attempt to consume tokens.
        Returns: (allowed: bool, remaining_tokens: int, retry_after_seconds: float)
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now

            # Refill tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))

            if self.tokens >= tokens_to_consume:
                self.tokens -= tokens_to_consume
                remaining = int(self.tokens)
                return True, remaining, 0.0
            else:
                # Calculate time required to accumulate tokens_to_consume
                deficit = tokens_to_consume - self.tokens
                retry_after = deficit / self.refill_rate if self.refill_rate > 0 else 1.0
                return False, int(self.tokens), retry_after


class RateLimiter:
    """In-memory rate limiter registry managing token buckets per key."""

    def __init__(self, capacity: int = 5, refill_rate: float = 0.5):
        """Default: 5 token burst, 0.5 tokens/sec (1 token every 2 seconds)."""
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = threading.Lock()

    def _get_bucket(self, key: str) -> TokenBucket:
        with self.lock:
            if key not in self.buckets:
                self.buckets[key] = TokenBucket(self.capacity, self.refill_rate)
            return self.buckets[key]

    def check(self, key: str) -> Tuple[bool, int, float]:
        bucket = self._get_bucket(key)
        return bucket.consume(1.0)

    def cleanup_old_buckets(self):
        """Optional maintenance method to clear inactive buckets."""
        with self.lock:
            now = time.time()
            stale_keys = [
                k for k, b in self.buckets.items()
                if now - b.last_update > 3600
            ]
            for k in stale_keys:
                del self.buckets[k]


# Global rate limiter instances for payments endpoints
payment_create_limiter = RateLimiter(capacity=5, refill_rate=0.5)  # 5 burst, 1 req / 2s
payment_verify_limiter = RateLimiter(capacity=10, refill_rate=1.0)  # 10 burst, 1 req / 1s


async def limit_payment_create(request: Request):
    """FastAPI dependency for rate limiting payment creation."""
    client_ip = request.client.host if request.client else "unknown_client"
    key = f"pay_create:{client_ip}"
    allowed, remaining, retry_after = payment_create_limiter.check(key)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for payment creation. Please slow down.",
            headers={
                "Retry-After": str(max(1, int(round(retry_after)))),
                "X-RateLimit-Limit": str(payment_create_limiter.capacity),
                "X-RateLimit-Remaining": "0",
            },
        )


async def limit_payment_verify(request: Request):
    """FastAPI dependency for rate limiting payment verification."""
    client_ip = request.client.host if request.client else "unknown_client"
    key = f"pay_verify:{client_ip}"
    allowed, remaining, retry_after = payment_verify_limiter.check(key)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for payment verification.",
            headers={
                "Retry-After": str(max(1, int(round(retry_after)))),
                "X-RateLimit-Limit": str(payment_verify_limiter.capacity),
                "X-RateLimit-Remaining": "0",
            },
        )
