"""Payment Service — state machine orchestrator and dual-verification convergence engine."""

import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User, BuyerProfile
from app.models.product import Product
from app.models.merchant import Merchant
from app.models.audit import AuditLog
from app.payments.razorpay_service import RazorpayService
from app.core.config import get_settings
from app.core.logging_middleware import get_current_request_id

logger = logging.getLogger("agentpay.payment_service")
settings = get_settings()


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.razorpay_svc = RazorpayService()

    async def create_payment_intent(self, order_id: str) -> Dict[str, Any]:
        """Initiate payment for an order by creating a Razorpay gateway order."""
        # 1. Fetch Order
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )

        if order.status == "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Order requires human approval in Trust Center before payment can be initiated.",
            )

        if order.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order has been cancelled: {order.failure_reason or 'No reason specified'}.",
            )

        if order.status == "success":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid and completed.",
            )

        # 2. Fetch Merchant & Product info
        prod = (
            await self.db.execute(select(Product).where(Product.id == order.product_id))
        ).scalar_one_or_none()
        product_name = prod.name if prod else "AgentPay Product"

        merch = (
            await self.db.execute(select(Merchant).where(Merchant.id == order.merchant_id))
        ).scalar_one_or_none()
        merchant_name = merch.name if merch else "AgentPay Merchant"

        # 3. Create Razorpay order (protected by Circuit Breaker)
        rp_order = self.razorpay_svc.create_order(
            amount_in_rupees=order.amount,
            receipt=f"rcpt_{order.id[:8]}",
            notes={
                "order_id": order.id,
                "session_id": order.session_id,
                "buyer_id": order.buyer_id,
            },
        )

        # 4. Update Order with razorpay_order_id & transition to pending
        order.razorpay_order_id = rp_order["razorpay_order_id"]
        order.status = "pending"

        # 5. Create Payment record in 'created' status
        payment = Payment(
            order_id=order.id,
            amount=order.amount,
            currency="INR",
            status="created",
        )
        self.db.add(payment)

        # 6. Audit log
        audit = AuditLog(
            session_id=order.session_id,
            actor="payment_service",
            action="payment_intent_created",
            reason=f"Created Razorpay order {rp_order['razorpay_order_id']} for ₹{order.amount:,.2f}",
            amount=order.amount,
            approval_status="approved",
            metadata_json={
                "order_id": order.id,
                "razorpay_order_id": rp_order["razorpay_order_id"],
                "request_id": get_current_request_id(),
            },
        )
        self.db.add(audit)
        await self.db.flush()

        return {
            "payment_id": payment.id,
            "order_id": order.id,
            "razorpay_order_id": rp_order["razorpay_order_id"],
            "razorpay_key_id": settings.razorpay_key_id or "rzp_test_mock_key_12345",
            "amount": rp_order["amount"],
            "currency": "INR",
            "merchant_name": merchant_name,
            "product_name": product_name,
        }

    async def process_payment_success(
        self,
        order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        source: str = "client_verify",
    ) -> Dict[str, Any]:
        """Dual-verification convergence engine.
        
        Safely reconciles state whether triggered by client-side /verify or server-to-server webhook.
        Guarantees that side effects (daily_spent update, audit log) execute EXACTLY ONCE.
        """
        # 1. Fetch Order
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            # Try finding order by razorpay_order_id
            order_res = await self.db.execute(
                select(Order).where(Order.razorpay_order_id == order_id)
            )
            order = order_res.scalar_one_or_none()

        if not order:
            logger.error(f"[PaymentConvergence] Order not found for identifier: {order_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )

        # 2. Check if already converged to success
        if order.status == "success":
            logger.info(
                f"[PaymentConvergence] Order {order.id} is ALREADY marked success. "
                f"Dual-path '{source}' converged safely without duplicating side-effects."
            )
            # Find associated payment
            pay_res = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payment = pay_res.scalars().first()
            return {
                "order_id": order.id,
                "payment_id": payment.id if payment else "n/a",
                "status": "success",
                "amount": order.amount,
                "message": f"Payment already confirmed (converged via {source})",
                "verified": True,
                "already_processed": True,
            }

        # 3. Transition Order to 'success'
        order.status = "success"
        order.failure_reason = None

        # 4. Find or create Payment record and update to success
        pay_res = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment = pay_res.scalars().first()

        if payment:
            payment.status = "success"
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
        else:
            payment = Payment(
                order_id=order.id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                amount=order.amount,
                currency="INR",
                status="success",
            )
            self.db.add(payment)

        await self.db.flush()

        # 5. Update Buyer's Daily Spent limit in BuyerProfile
        buyer_profile_res = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == order.buyer_id)
        )
        buyer_profile = buyer_profile_res.scalar_one_or_none()
        if buyer_profile:
            buyer_profile.daily_spent += order.amount
            logger.info(
                f"[PaymentService] Updated buyer {order.buyer_id} daily_spent to ₹{buyer_profile.daily_spent:,.2f}"
            )

        # 6. Record Audit Log for successful payment settlement
        audit = AuditLog(
            session_id=order.session_id,
            actor=source,
            action="payment_verified_and_settled",
            reason=f"Payment verified via {source} for amount ₹{order.amount:,.2f}",
            amount=order.amount,
            approval_status="approved",
            metadata_json={
                "order_id": order.id,
                "payment_id": payment.id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_order_id": order.razorpay_order_id,
                "source": source,
                "request_id": get_current_request_id(),
            },
        )
        self.db.add(audit)
        await self.db.flush()

        logger.info(
            f"[PaymentConvergence] Successfully verified & converged order {order.id} via {source}"
        )
        return {
            "order_id": order.id,
            "payment_id": payment.id,
            "status": "success",
            "amount": order.amount,
            "message": f"Payment successfully verified and captured via {source}",
            "verified": True,
            "already_processed": False,
        }

    async def process_payment_failure(
        self, order_id: str, reason: str, source: str = "client_verify"
    ) -> Dict[str, Any]:
        """Handle payment failure event gracefully with retry capability."""
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            order_res = await self.db.execute(
                select(Order).where(Order.razorpay_order_id == order_id)
            )
            order = order_res.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )

        # Do not override terminal success
        if order.status == "success":
            logger.warning(
                f"[PaymentService] Ignoring failure event for already successful order {order.id}"
            )
            return {"order_id": order.id, "status": "success", "ignored": True}

        order.status = "failed"
        order.failure_reason = reason

        pay_res = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment = pay_res.scalars().first()
        if payment:
            payment.status = "failed"
            payment.failure_reason = reason

        audit = AuditLog(
            session_id=order.session_id,
            actor=source,
            action="payment_failed",
            reason=f"Payment failed via {source}: {reason}",
            amount=order.amount,
            approval_status="rejected",
            metadata_json={"order_id": order.id, "reason": reason, "source": source},
        )
        self.db.add(audit)
        await self.db.flush()

        return {
            "order_id": order.id,
            "status": "failed",
            "failure_reason": reason,
            "can_retry": True,
            "message": f"Payment failed: {reason}. You can retry payment.",
        }
