"""Integration tests for Reconciliation Engine."""

import pytest
from app.models.order import Order
from app.models.payment import Payment
from app.services.reconciliation_service import ReconciliationService
from sqlalchemy import select


@pytest.mark.asyncio
async def test_reconciliation_detects_clean_ledger(client, db_session, seed_data):
    """Test reconciliation reporting 100% health when all orders and payments match."""
    quote = seed_data["quote"]
    # Create and complete order
    ord_res = await client.post(
        "/api/orders",
        json={"quote_id": quote.id, "session_id": "sess-recon-1", "user_id": "demo-user-001"},
    )
    order_id = ord_res.json()["id"]
    await client.post(f"/api/policy/approvals/{order_id}/approve")

    pay_res = await client.post("/api/payments/create", json={"order_id": order_id})
    rzp_order_id = pay_res.json()["razorpay_order_id"]

    await client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "razorpay_payment_id": "pay_test_recon_1",
            "razorpay_order_id": rzp_order_id,
            "razorpay_signature": "sig_valid_test_recon",
        },
    )

    # Run reconciliation via API
    recon_res = await client.post("/api/reconciliation/run?lookback_hours=24")
    assert recon_res.status_code == 200
    report = recon_res.json()
    assert report["total_orders_checked"] >= 1
    assert report["discrepancies_flagged"] == 0
    assert report["health_score_percent"] == 100.0


@pytest.mark.asyncio
async def test_reconciliation_flags_discrepancy_and_auto_heals(db_session, seed_data):
    """Test reconciliation auto-healing a missed webhook on a pending order."""
    quote = seed_data["quote"]
    
    # Create an order in pending state with simulated gateway order
    order = Order(
        buyer_id="demo-user-001",
        merchant_id=quote.merchant_id,
        product_id=quote.product_id,
        quote_id=quote.id,
        session_id="sess-heal-1",
        amount=67500.0,
        currency="INR",
        status="pending",
        razorpay_order_id="order_test_recon_heal_99",
    )
    db_session.add(order)
    await db_session.commit()

    recon_svc = ReconciliationService(db_session)
    report = await recon_svc.run_reconciliation(lookback_hours=24, auto_heal=True)

    # Should have auto-healed the missed webhook
    assert report["auto_healed_orders"] >= 1
    
    # Verify order in DB transitioned to 'success'
    updated_order = (
        await db_session.execute(select(Order).where(Order.id == order.id))
    ).scalar_one()
    assert updated_order.status == "success"
