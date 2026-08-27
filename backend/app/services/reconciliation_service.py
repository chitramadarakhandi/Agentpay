"""Reconciliation Service — audit ledger vs gateway consistency cross-checker and money conservation invariant engine."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.order import Order
from app.models.payment import Payment
from app.models.user import BuyerProfile
from app.models.audit import AuditLog
from app.payments.razorpay_service import RazorpayService
from app.services.payment_service import PaymentService
from app.core.logging_middleware import get_current_request_id

logger = logging.getLogger("agentpay.reconciliation")


class ReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.razorpay_svc = RazorpayService()
        self.payment_svc = PaymentService(db)

    async def run_reconciliation(
        self,
        lookback_hours: int = 24,
        auto_heal: bool = True,
    ) -> Dict[str, Any]:
        """Execute reconciliation batch across internal DB orders, payment logs, and gateway status."""
        now = datetime.now(timezone.utc)
        since_time = now - timedelta(hours=lookback_hours)

        # 1. Query orders within window
        result = await self.db.execute(
            select(Order).where(Order.created_at >= since_time)
        )
        orders = list(result.scalars().all())

        matched = []
        discrepancies = []
        auto_healed = []

        for order in orders:
            # Query payments associated with order
            pay_res = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payments = list(pay_res.scalars().all())
            latest_payment = payments[-1] if payments else None

            # Fetch gateway status if razorpay_order_id exists
            gateway_order = None
            if order.razorpay_order_id:
                gateway_order = self.razorpay_svc.fetch_order(order.razorpay_order_id)

            gateway_status = gateway_order.get("status") if gateway_order else "unknown"

            # Check 1: Normal matched success
            if order.status == "success":
                if latest_payment and latest_payment.status == "success":
                    matched.append({
                        "order_id": order.id,
                        "amount": order.amount,
                        "status": "success",
                        "gateway_status": gateway_status,
                    })
                else:
                    # DB Order marked success but no successful payment log
                    discrepancies.append({
                        "order_id": order.id,
                        "type": "MISSING_PAYMENT_RECORD",
                        "severity": "HIGH",
                        "details": f"Order {order.id} is marked 'success' but payment record status is '{latest_payment.status if latest_payment else 'None'}'",
                        "action_required": "Investigate transaction ledger",
                    })

            # Check 2: Pending order that is actually paid at gateway (Missed Webhook)
            elif order.status == "pending":
                if gateway_status == "paid":
                    if auto_heal:
                        # Auto-heal missed webhook
                        heal_res = await self.payment_svc.process_payment_success(
                            order_id=order.id,
                            razorpay_payment_id=f"pay_recon_{order.id[:8]}",
                            razorpay_signature="recon_auto_healed",
                            source="reconciliation_auto_heal",
                        )
                        auto_healed.append({
                            "order_id": order.id,
                            "type": "MISSED_WEBHOOK_HEALED",
                            "details": f"Order {order.id} was 'pending' in DB but 'paid' on Gateway. Automatically settled.",
                        })
                    else:
                        discrepancies.append({
                            "order_id": order.id,
                            "type": "UNSETTLED_GATEWAY_PAYMENT",
                            "severity": "MEDIUM",
                            "details": f"Order {order.id} is pending in DB but paid at Gateway.",
                            "action_required": "Trigger manual settlement or verify webhook health",
                        })
                else:
                    # Check for stale pending (> 30 mins)
                    created_at = order.created_at
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    if now - created_at > timedelta(minutes=30):
                        discrepancies.append({
                            "order_id": order.id,
                            "type": "STALE_PENDING_ORDER",
                            "severity": "LOW",
                            "details": f"Order {order.id} has been pending for over 30 minutes without completion.",
                            "action_required": "Consider marking order as cancelled or expired",
                        })
                    else:
                        matched.append({
                            "order_id": order.id,
                            "amount": order.amount,
                            "status": "pending_active",
                            "gateway_status": gateway_status,
                        })

            # Check 3: Failed orders
            elif order.status == "failed":
                matched.append({
                    "order_id": order.id,
                    "amount": order.amount,
                    "status": "failed",
                    "failure_reason": order.failure_reason,
                })

        # Summary statistics
        total_checked = len(orders)
        matched_count = len(matched)
        discrepancy_count = len(discrepancies)
        healed_count = len(auto_healed)

        report = {
            "reconciliation_id": f"recon_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "executed_at": now.isoformat(),
            "lookback_hours": lookback_hours,
            "total_orders_checked": total_checked,
            "matched_orders": matched_count,
            "discrepancies_flagged": discrepancy_count,
            "auto_healed_orders": healed_count,
            "health_score_percent": round(
                ((matched_count + healed_count) / total_checked * 100) if total_checked > 0 else 100.0,
                2,
            ),
            "discrepancies": discrepancies,
            "auto_healed": auto_healed,
        }

        # Record Audit Log for reconciliation run
        audit = AuditLog(
            session_id="system_reconciliation",
            actor="reconciliation_job",
            action="reconciliation_completed",
            reason=f"Reconciliation checked {total_checked} orders: {matched_count} matched, {discrepancy_count} flagged, {healed_count} auto-healed",
            approval_status="approved",
            metadata_json=report,
        )
        self.db.add(audit)
        await self.db.flush()

        logger.info(
            f"[Reconciliation] Finished: {total_checked} checked, {discrepancy_count} discrepancies, {healed_count} auto-healed."
        )
        return report

    async def check_money_conservation_invariant(self) -> Dict[str, Any]:
        """
        Fintech Invariant Check: Money Conservation & Zero-Drift Assertion.
        
        Double-Entry conservation rule:
        Sum(Orders where status='success') == Sum(Payments where status='success')
        
        Returns:
            Structured invariant audit proving zero drift (delta = 0.00).
        """
        # Sum of successful orders
        order_sum_res = await self.db.execute(
            select(func.coalesce(func.sum(Order.amount), 0.0)).where(Order.status == "success")
        )
        total_order_amount = round(float(order_sum_res.scalar_one()), 2)

        # Sum of successful verified payments
        pay_sum_res = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.status == "success")
        )
        total_payment_amount = round(float(pay_sum_res.scalar_one()), 2)

        # Sum of buyer daily_spent
        buyer_spent_res = await self.db.execute(
            select(func.coalesce(func.sum(BuyerProfile.daily_spent), 0.0))
        )
        total_buyer_spent = round(float(buyer_spent_res.scalar_one()), 2)

        # Invariant drift calculation
        drift = round(abs(total_order_amount - total_payment_amount), 2)
        invariant_holds = (drift == 0.0)

        # Counts
        order_count_res = await self.db.execute(
            select(func.count(Order.id)).where(Order.status == "success")
        )
        successful_orders_count = order_count_res.scalar_one()

        pay_count_res = await self.db.execute(
            select(func.count(Payment.id)).where(Payment.status == "success")
        )
        successful_payments_count = pay_count_res.scalar_one()

        report = {
            "invariant_name": "MONEY_CONSERVATION_ZERO_DRIFT",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "invariant_holds": invariant_holds,
            "drift_amount": drift,
            "drift_currency": "INR",
            "audit_ledger": {
                "total_successful_order_amount": total_order_amount,
                "total_successful_orders_count": successful_orders_count,
                "total_verified_payment_amount": total_payment_amount,
                "total_verified_payments_count": successful_payments_count,
                "total_buyer_daily_spent": total_buyer_spent,
            },
            "mathematical_assertion": f"Σ(Orders.amount) [₹{total_order_amount:,.2f}] == Σ(Payments.amount) [₹{total_payment_amount:,.2f}] => Δ = ₹{drift:,.2f}",
            "status": "PASS" if invariant_holds else "CRITICAL_DRIFT_ALERT",
        }

        if not invariant_holds:
            logger.critical(f"[MoneyConservation] INVARIANT BREACHED! Drift: ₹{drift:,.2f}")
        else:
            logger.info(f"[MoneyConservation] Invariant Verified. Zero drift confirmed (₹{total_order_amount:,.2f}).")

        return report
