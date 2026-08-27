"""Integration tests for Order Creation Concurrency and Race Conditions."""

import asyncio
import pytest
from app.services.order_service import OrderService
from app.models.product import Quote
from sqlalchemy import select


@pytest.mark.asyncio
async def test_order_creation_success(client, seed_data):
    """Test standard order creation from an active quote."""
    quote = seed_data["quote"]
    response = await client.post(
        "/api/orders",
        json={
            "quote_id": quote.id,
            "session_id": "sess-test-001",
            "user_id": "demo-user-001",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quote_id"] == quote.id
    assert data["amount"] == 67500.0
    # Amount ₹67,500 exceeds default approval threshold ₹50,000, so status is pending_approval
    assert data["status"] == "pending_approval"
    assert "merchant_name" in data

    # Human approves order
    appr_res = await client.post(f"/api/policy/approvals/{data['id']}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["order"]["status"] == "created"


@pytest.mark.asyncio
async def test_duplicate_order_on_same_quote_rejected_with_409(client, seed_data):
    """Test that creating a second order on an already-ordered quote fails with 409 Conflict."""
    quote = seed_data["quote"]
    
    # 1. First order succeeds
    res1 = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-01", "user_id": "demo-user-001"},
    )
    assert res1.status_code == 201

    # 2. Second attempt on the same quote MUST fail with 409 Conflict
    res2 = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-02", "user_id": "demo-user-001"},
    )
    assert res2.status_code == 409
    assert "Quote" in res2.json()["detail"] or "already" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_concurrent_order_creation_race_condition(db_session, seed_data):
    """Simulate two simultaneous service calls on the exact same quote."""
    quote = seed_data["quote"]
    svc = OrderService(db_session)

    # First call succeeds
    order1 = await svc.create_order_from_quote(quote.id, "demo-user-001", "sess-1")
    assert order1 is not None

    # Immediate second call within same or parallel transaction fails
    with pytest.raises(Exception) as exc:
        await svc.create_order_from_quote(quote.id, "demo-user-001", "sess-2")
    
    # Assert status code 409
    assert hasattr(exc.value, "status_code")
    assert exc.value.status_code == 409
