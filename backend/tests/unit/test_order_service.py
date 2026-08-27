"""Unit tests for OrderService edge cases."""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from app.services.order_service import OrderService
from app.models.product import Quote


@pytest.mark.asyncio
async def test_create_order_nonexistent_quote(db_session):
    svc = OrderService(db_session)
    with pytest.raises(HTTPException) as exc:
        await svc.create_order_from_quote("quote_does_not_exist")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_order_expired_quote(db_session, seed_data):
    quote = seed_data["quote"]
    quote.valid_until = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    svc = OrderService(db_session)
    with pytest.raises(HTTPException) as exc:
        await svc.create_order_from_quote(quote.id)
    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_create_order_inactive_quote(db_session, seed_data):
    quote = seed_data["quote"]
    quote.status = "rejected"
    await db_session.commit()

    svc = OrderService(db_session)
    with pytest.raises(HTTPException) as exc:
        await svc.create_order_from_quote(quote.id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_get_and_list_orders(db_session, seed_data):
    quote = seed_data["quote"]
    svc = OrderService(db_session)
    order = await svc.create_order_from_quote(quote.id, "demo-user-001")

    # Get by ID
    fetched = await svc.get_order_by_id(order.id)
    assert fetched is not None
    assert fetched.id == order.id

    # Enrich
    enriched = await svc.enrich_order(fetched)
    assert enriched["merchant_name"] == "TechNova India"
    assert enriched["product_name"] == "TechNova Pro 16"

    # List
    orders = await svc.list_orders(user_id="demo-user-001")
    assert len(orders) >= 1


@pytest.mark.asyncio
async def test_order_approval_gate_and_transitions(db_session, seed_data):
    quote = seed_data["quote"]
    # TechNova Pro 16 price in seed data is ₹75,000, which exceeds default requires_approval_above (₹50,000)
    svc = OrderService(db_session)
    order = await svc.create_order_from_quote(quote.id, "demo-user-001")

    # Verify initial gated state
    assert order.status == "pending_approval"
    assert order.metadata_json.get("requires_human_approval") is True
    assert order.metadata_json.get("approval_token") is not None

    # Verify pending approvals listing
    pending = await svc.list_pending_approvals()
    assert any(p.id == order.id for p in pending)

    # Approve order
    approved = await svc.approve_order(order.id, approver="test_admin")
    assert approved.status == "created"
    assert approved.metadata_json.get("approval_status") == "human_approved"

    # Pending list should now no longer contain the approved order
    pending_after = await svc.list_pending_approvals()
    assert not any(p.id == order.id for p in pending_after)

