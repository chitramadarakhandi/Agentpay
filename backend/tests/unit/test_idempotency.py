"""Unit tests for Idempotency Service with TTL."""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from app.services.idempotency_service import IdempotencyService
from app.models.idempotency import IdempotencyRecord


@pytest.mark.asyncio
async def test_new_idempotency_key_starts_pending(db_session):
    svc = IdempotencyService(db_session)
    key = "test_key_001"
    endpoint = "/api/orders"
    payload = {"quote_id": "q1", "user_id": "u1"}

    # First call should return None (new key, caller should process)
    cached = await svc.check_and_start(key, endpoint, payload)
    assert cached is None


@pytest.mark.asyncio
async def test_completed_idempotency_key_replays_cached_response(db_session):
    svc = IdempotencyService(db_session)
    key = "test_key_002"
    endpoint = "/api/orders"
    payload = {"quote_id": "q2", "user_id": "u1"}

    await svc.check_and_start(key, endpoint, payload)
    
    # Complete execution and store response
    response_data = {"order_id": "ord_123", "status": "created", "amount": 5000}
    await svc.complete(key, response_code=201, response_body=response_data)

    # Replaying same request returns cached response immediately
    cached = await svc.check_and_start(key, endpoint, payload)
    assert cached is not None
    code, body = cached
    assert code == 201
    assert body["order_id"] == "ord_123"


@pytest.mark.asyncio
async def test_in_flight_pending_request_raises_conflict(db_session):
    svc = IdempotencyService(db_session)
    key = "test_key_003"
    endpoint = "/api/payments/create"
    payload = {"order_id": "ord_456"}

    # First request starts PENDING
    await svc.check_and_start(key, endpoint, payload)

    # Parallel second request before completion raises 409
    with pytest.raises(HTTPException) as exc_info:
        await svc.check_and_start(key, endpoint, payload)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_altered_payload_with_same_key_raises_422(db_session):
    svc = IdempotencyService(db_session)
    key = "test_key_004"
    endpoint = "/api/payments/create"
    payload_a = {"order_id": "ord_1"}
    payload_b = {"order_id": "ord_2"}

    await svc.check_and_start(key, endpoint, payload_a)

    with pytest.raises(HTTPException) as exc_info:
        await svc.check_and_start(key, endpoint, payload_b)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_expired_key_is_purged_and_allowed(db_session):
    svc = IdempotencyService(db_session)
    key = "test_key_005"
    endpoint = "/api/orders"
    payload = {"quote_id": "q5"}

    # Insert an already expired record
    expired_record = IdempotencyRecord(
        key=key,
        request_hash=svc.compute_hash(endpoint, payload),
        status="COMPLETED",
        response_code=200,
        response_body={"old": True},
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(expired_record)
    await db_session.commit()

    # check_and_start should detect expiration, delete stale record, and treat as new
    cached = await svc.check_and_start(key, endpoint, payload)
    assert cached is None
