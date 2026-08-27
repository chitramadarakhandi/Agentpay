"""Integration tests for Dual-Path Payment Convergence and Webhook Idempotency."""

import pytest
from app.models.payment import Payment
from app.models.order import Order
from app.models.user import BuyerProfile
from sqlalchemy import select


@pytest.mark.asyncio
async def test_payment_creation_and_tracing_header(client, seed_data):
    """Test payment creation returns Razorpay order details and X-Request-ID header."""
    quote = seed_data["quote"]
    # 1. Create order
    ord_res = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-pay-1", "user_id": "demo-user-001"},
    )
    order_id = ord_res.json()["id"]
    await client.post(f"/api/policy/approvals/{order_id}/approve")

    # 2. Create payment
    pay_res = await client.post(
        "/api/payments/create",
        json={"order_id": order_id},
        headers={"X-Request-ID": "req_custom_trace_999"},
    )
    assert pay_res.status_code == 200
    pay_data = pay_res.json()
    assert pay_data["order_id"] == order_id
    assert "razorpay_order_id" in pay_data
    assert pay_res.headers.get("X-Request-ID") == "req_custom_trace_999"


@pytest.mark.asyncio
async def test_dual_convergence_webhook_first_then_client_verify(client, db_session, seed_data):
    """Test scenario: Webhook arrives before client-side verify call.
    Both must succeed, but ledger / buyer spending must only be credited ONCE.
    """
    quote = seed_data["quote"]
    ord_res = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-conv-1", "user_id": "demo-user-001"},
    )
    order_id = ord_res.json()["id"]
    await client.post(f"/api/policy/approvals/{order_id}/approve")

    pay_res = await client.post("/api/payments/create", json={"order_id": order_id})
    razorpay_order_id = pay_res.json()["razorpay_order_id"]

    # Step 1: Gateway Webhook Arrives First
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_wh_12345",
                    "order_id": razorpay_order_id,
                    "amount": 6750000,
                    "notes": {"order_id": order_id},
                }
            }
        },
    }
    wh_res = await client.post("/api/payments/webhook", json=webhook_payload)
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "processed"

    # Verify Order is marked success
    order_in_db = (
        await db_session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert order_in_db.status == "success"

    # Step 2: Client-side /verify fires subsequently
    verify_res = await client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "razorpay_payment_id": "pay_test_wh_12345",
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": "sig_valid_test_signature",
        },
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["status"] == "success"
    assert v_data["already_processed"] is True  # Converged safely!

    # Step 3: Verify Buyer Daily Spent was incremented ONLY ONCE
    profile = (
        await db_session.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == "demo-user-001")
        )
    ).scalar_one()
    assert profile.daily_spent == 67500.0


@pytest.mark.asyncio
async def test_dual_convergence_client_verify_first_then_webhook(client, db_session, seed_data):
    """Test scenario: Client-side verify arrives first, followed by Webhook."""
    quote = seed_data["quote"]
    ord_res = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-conv-2", "user_id": "demo-user-001"},
    )
    order_id = ord_res.json()["id"]
    await client.post(f"/api/policy/approvals/{order_id}/approve")

    pay_res = await client.post("/api/payments/create", json={"order_id": order_id})
    razorpay_order_id = pay_res.json()["razorpay_order_id"]

    # Step 1: Client Verify fires first
    verify_res = await client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "razorpay_payment_id": "pay_client_first_999",
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": "sig_client_valid_mock",
        },
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["already_processed"] is False

    # Step 2: Webhook arrives second
    webhook_payload = {
        "event": "order.paid",
        "payload": {
            "order": {
                "entity": {
                    "id": razorpay_order_id,
                    "amount": 6750000,
                    "notes": {"order_id": order_id},
                }
            }
        },
    }
    wh_res = await client.post("/api/payments/webhook", json=webhook_payload)
    assert wh_res.status_code == 200
    assert wh_res.json()["result"]["already_processed"] is True

    # Check buyer daily spent is exact amount once
    profile = (
        await db_session.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == "demo-user-001")
        )
    ).scalar_one()
    assert profile.daily_spent == 67500.0
