"""Refund lifecycle, state machine, and money-conservation tests."""

import asyncio
import pytest
from fastapi import HTTPException

from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.services.refund_service import RefundService


async def paid_order(db_session, amount=1000.0, category="laptops"):
    product = Product(
        id="product-refund-01",
        merchant_id="merchant-01",
        name="Test Laptop",
        description="Test Laptop",
        category=category,
        price=amount,
        stock=10,
        active=True,
    )
    order = Order(
        id="order-refund-01",
        buyer_id="demo-user-001",
        merchant_id="merchant-01",
        product_id=product.id,
        session_id="refund-session-01",
        amount=amount,
        currency="INR",
        status="success",
    )
    payment = Payment(
        id="payment-refund-01",
        order_id=order.id,
        razorpay_payment_id="pay_test_01",
        amount=amount,
        currency="INR",
        status="success",
    )
    db_session.add_all([product, order, payment])
    await db_session.commit()
    return order, payment


@pytest.mark.asyncio
async def test_full_and_partial_refunds_conserve_money(db_session):
    order, payment = await paid_order(db_session, amount=1000.0)
    service = RefundService(db_session)

    # 1. First partial refund: request ₹250 -> approve -> processed
    first_req = await service.request_refund(
        order.id, payment.id, 250.0, "Partial return", "refund-key-01"
    )
    assert first_req["status"] == "pending_approval"
    assert first_req["amount"] == 250.0

    first_app = await service.approve_refund(first_req["id"])
    assert first_app["status"] == "processed"
    assert first_app["refunded_amount"] == 250.0
    assert first_app["remaining_refundable_amount"] == 750.0

    # 2. Second refund: request remaining ₹750 -> approve -> processed
    second_req = await service.request_refund(
        order.id, payment.id, 750.0, "Final return", "refund-key-02"
    )
    assert second_req["status"] == "pending_approval"

    second_app = await service.approve_refund(second_req["id"])
    assert second_app["status"] == "processed"
    assert second_app["remaining_refundable_amount"] == 0.0
    assert second_app["refunded_amount"] == 1000.0


@pytest.mark.asyncio
async def test_over_refund_is_rejected_and_retry_is_idempotent(db_session):
    order, payment = await paid_order(db_session, amount=1000.0)
    service = RefundService(db_session)

    # Over-refund attempt
    with pytest.raises(HTTPException) as exc:
        await service.request_refund(order.id, payment.id, 1000.01, "Too much", "refund-key-03")
    assert exc.value.status_code == 400

    # Idempotent request
    first = await service.request_refund(order.id, payment.id, 100.0, "Retry me", "refund-key-04")
    retry = await service.request_refund(order.id, payment.id, 100.0, "Retry me", "refund-key-04")
    assert retry["id"] == first["id"]
    assert retry["amount"] == 100.0


@pytest.mark.asyncio
async def test_merchant_reject_flow(db_session):
    order, payment = await paid_order(db_session, amount=500.0)
    service = RefundService(db_session)

    req = await service.request_refund(order.id, payment.id, 500.0, "Changed mind", "refund-key-05")
    assert req["status"] == "pending_approval"

    rejected = await service.reject_refund(req["id"], "Outside policy return scope.")
    assert rejected["status"] == "rejected"
    assert rejected["failure_reason"] == "Outside policy return scope."


@pytest.mark.asyncio
async def test_invalid_order_and_unpaid_payment_are_rejected(db_session):
    service = RefundService(db_session)
    with pytest.raises(HTTPException) as missing:
        await service.request_refund("missing-order-999", None, 10, "Missing", "refund-key-06")
    assert missing.value.status_code == 404

    order = Order(
        id="order-unpaid-01", buyer_id="demo-user-001", merchant_id="merchant-01",
        product_id="product-01", session_id="refund-session-02", amount=100.0, status="pending",
    )
    db_session.add(order)
    await db_session.commit()
    with pytest.raises(HTTPException) as unpaid:
        await service.request_refund(order.id, None, 10, "Not paid", "refund-key-07")
    assert unpaid.value.status_code == 400
