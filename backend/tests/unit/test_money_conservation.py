"""Unit tests for Fintech Money Conservation Invariant (Zero-Drift Invariant Engine)."""

import pytest
from app.models.order import Order
from app.models.payment import Payment
from app.services.reconciliation_service import ReconciliationService


@pytest.mark.asyncio
async def test_money_conservation_invariant_holds_under_successful_transactions(db_session, seed_data):
    """
    Assert invariant: Sum(Orders[success]) == Sum(Payments[success])
    Zero drift must hold: delta == 0.00.
    """
    quote = seed_data["quote"]

    # Insert 3 successful orders with matching payments
    for i in range(3):
        amount = 10000.0 * (i + 1)
        order = Order(
            id=f"ord_inv_{i}",
            buyer_id="demo-user-001",
            merchant_id=quote.merchant_id,
            product_id=quote.product_id,
            session_id=f"sess_inv_{i}",
            amount=amount,
            currency="INR",
            status="success",
        )
        db_session.add(order)

        payment = Payment(
            id=f"pay_inv_{i}",
            order_id=order.id,
            razorpay_payment_id=f"rp_inv_{i}",
            amount=amount,
            currency="INR",
            status="success",
        )
        db_session.add(payment)

    # Insert 1 failed order and 1 pending order (should not affect success sums)
    db_session.add(Order(id="ord_fail", buyer_id="demo-user-001", merchant_id=quote.merchant_id, product_id=quote.product_id, session_id="s_f", amount=50000.0, status="failed"))
    db_session.add(Order(id="ord_pend", buyer_id="demo-user-001", merchant_id=quote.merchant_id, product_id=quote.product_id, session_id="s_p", amount=20000.0, status="pending"))

    await db_session.commit()

    recon_svc = ReconciliationService(db_session)
    report = await recon_svc.check_money_conservation_invariant()

    assert report["invariant_holds"] is True
    assert report["drift_amount"] == 0.0
    assert report["audit_ledger"]["total_successful_order_amount"] == 60000.0
    assert report["audit_ledger"]["total_verified_payment_amount"] == 60000.0
    assert report["status"] == "PASS"


@pytest.mark.asyncio
async def test_money_conservation_detects_financial_drift(db_session, seed_data):
    """Assert invariant engine catches synthetic financial drift (ledger tampering/leak)."""
    quote = seed_data["quote"]

    # Order amount is 50,000 but payment captured was 40,000 (drift = 10,000)
    order = Order(
        id="ord_drift_01",
        buyer_id="demo-user-001",
        merchant_id=quote.merchant_id,
        product_id=quote.product_id,
        session_id="sess_drift",
        amount=50000.0,
        currency="INR",
        status="success",
    )
    payment = Payment(
        id="pay_drift_01",
        order_id=order.id,
        amount=40000.0,  # Intentional discrepancy
        currency="INR",
        status="success",
    )
    db_session.add(order)
    db_session.add(payment)
    await db_session.commit()

    recon_svc = ReconciliationService(db_session)
    report = await recon_svc.check_money_conservation_invariant()

    assert report["invariant_holds"] is False
    assert report["drift_amount"] == 10000.0
    assert report["status"] == "CRITICAL_DRIFT_ALERT"
