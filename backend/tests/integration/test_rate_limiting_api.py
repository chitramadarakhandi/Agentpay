"""Integration tests for Payment Endpoints Rate Limiting."""

import pytest
from app.core.rate_limiter import payment_create_limiter


@pytest.mark.asyncio
async def test_payment_create_endpoint_rate_limiting(client, seed_data):
    """Verify that rapid requests to /api/payments/create trigger HTTP 429 with Retry-After header."""
    quote = seed_data["quote"]
    ord_res = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-rl-1", "user_id": "demo-user-001"},
    )
    order_id = ord_res.json()["id"]

    # Reset bucket tokens for test isolation
    payment_create_limiter.buckets.clear()

    # 5 requests should pass (capacity is 5)
    for _ in range(5):
        res = await client.post("/api/payments/create", json={"order_id": order_id})
        # Could be 200 or 400 (if order already pending), but not 429
        assert res.status_code != 429

    # 6th immediate request MUST be rate limited with 429
    limited_res = await client.post("/api/payments/create", json={"order_id": order_id})
    assert limited_res.status_code == 429
    assert "Rate limit exceeded" in limited_res.json()["detail"]
    assert "Retry-After" in limited_res.headers
