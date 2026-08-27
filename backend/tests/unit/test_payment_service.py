"""Unit tests for PaymentService lifecycle and failure handling."""

import pytest
from fastapi import HTTPException
from app.services.payment_service import PaymentService
from app.services.order_service import OrderService


@pytest.mark.asyncio
async def test_create_payment_intent_for_order(db_session, seed_data):
    quote = seed_data["quote"]
    order_svc = OrderService(db_session)
    order = await order_svc.create_order_from_quote(quote.id, "demo-user-001")

    pay_svc = PaymentService(db_session)

    # 1. Order is pending_approval, so payment creation must fail with HTTP 403
    with pytest.raises(HTTPException) as exc:
        await pay_svc.create_payment_intent(order.id)
    assert exc.value.status_code == 403
    assert "human approval" in exc.value.detail

    # 2. Approve the order
    await order_svc.approve_order(order.id, approver="test_admin")

    # 3. Payment creation succeeds after approval
    intent = await pay_svc.create_payment_intent(order.id)
    assert intent["order_id"] == order.id
    assert "razorpay_order_id" in intent
    assert intent["amount"] == 6750000  # in paise


@pytest.mark.asyncio
async def test_create_payment_for_completed_order_fails(db_session, seed_data):
    quote = seed_data["quote"]
    order_svc = OrderService(db_session)
    order = await order_svc.create_order_from_quote(quote.id, "demo-user-001")
    await order_svc.approve_order(order.id, approver="test_admin")

    pay_svc = PaymentService(db_session)
    await pay_svc.process_payment_success(order.id, "pay_mock_1", "sig_mock_1")

    with pytest.raises(HTTPException) as exc:
        await pay_svc.create_payment_intent(order.id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_process_payment_failure_flow(db_session, seed_data):
    quote = seed_data["quote"]
    order_svc = OrderService(db_session)
    order = await order_svc.create_order_from_quote(quote.id, "demo-user-001")

    pay_svc = PaymentService(db_session)
    fail_res = await pay_svc.process_payment_failure(
        order_id=order.id,
        reason="Bank server unavailable",
        source="razorpay_webhook",
    )
    assert fail_res["status"] == "failed"
    assert fail_res["can_retry"] is True
    assert order.status == "failed"
