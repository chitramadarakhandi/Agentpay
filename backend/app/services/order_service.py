"""Order Service — handles atomic order creation, concurrency locks, and state management."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.order import Order, utcnow
from app.models.product import Quote, Product
from app.models.merchant import Merchant
import secrets
from app.models.user import User, BuyerProfile
from app.models.audit import AuditLog
from app.models.payment import Payment
from app.core.logging_middleware import get_current_request_id

logger = logging.getLogger("agentpay.order_service")


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order_from_quote(
        self, quote_id: str, user_id: str = "demo-user-001", session_id: Optional[str] = None
    ) -> Order:
        """Atomically create an order from an accepted active quote.
        
        Guarantees concurrency safety and enforces Human-in-the-Loop approval gates
        when order amount exceeds the buyer's requires_approval_above threshold.
        """
        now = utcnow()

        # Step 1: Verify quote existence and validity
        result = await self.db.execute(
            select(Quote).where(Quote.id == quote_id)
        )
        quote = result.scalar_one_or_none()

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )

        # Check expiration (ensure tz awareness)
        valid_until = quote.valid_until
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        if valid_until < now:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=f"Quote '{quote_id}' has expired.",
            )

        if quote.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quote '{quote_id}' is no longer active (current status: {quote.status}).",
            )

        # Step 2: Atomic State Transition of Quote to 'accepted'
        update_stmt = (
            update(Quote)
            .where(Quote.id == quote_id, Quote.status == "active")
            .values(status="accepted")
        )
        update_result = await self.db.execute(update_stmt)
        if update_result.rowcount == 0:
            logger.warning(
                f"[Concurrency] Race condition detected: Quote {quote_id} was already claimed by another request."
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Quote has already been converted to an order by another concurrent request.",
            )

        # Step 3: Check Human-in-the-Loop Approval Threshold
        profile_res = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()
        threshold = profile.requires_approval_above if profile else 50000.0
        requires_approval = quote.final_price > threshold

        initial_status = "pending_approval" if requires_approval else "created"
        approval_token = secrets.token_urlsafe(24) if requires_approval else None

        metadata = {
            "original_price": quote.original_price,
            "discount_percent": quote.discount_percent,
            "discount_amount": quote.discount_amount,
            "request_id": get_current_request_id(),
            "requires_human_approval": requires_approval,
            "approval_threshold": threshold,
        }
        if requires_approval:
            metadata["approval_token"] = approval_token
            metadata["approval_status"] = "pending_human_review"
            metadata["approval_requested_at"] = now.isoformat()

        # Step 4: Create Order Record
        order = Order(
            buyer_id=user_id,
            merchant_id=quote.merchant_id,
            product_id=quote.product_id,
            quote_id=quote.id,
            session_id=session_id or quote.session_id,
            amount=quote.final_price,
            currency="INR",
            status=initial_status,
            metadata_json=metadata,
        )
        self.db.add(order)

        # Step 5: Write Audit Log
        if requires_approval:
            audit = AuditLog(
                session_id=order.session_id,
                actor="order_service",
                action="order_pending_approval",
                reason=f"Order amount ₹{order.amount:,.2f} exceeds human approval threshold ₹{threshold:,.2f}. Pending human sign-off.",
                amount=order.amount,
                approval_status="pending_human_review",
                metadata_json={
                    "order_id": order.id,
                    "quote_id": quote.id,
                    "approval_token": approval_token,
                    "threshold": threshold,
                },
            )
        else:
            audit = AuditLog(
                session_id=order.session_id,
                actor="order_service",
                action="order_created",
                reason=f"Order created from quote {quote.id} for ₹{order.amount:,.2f} (auto-approved within ₹{threshold:,.2f} threshold)",
                amount=order.amount,
                approval_status="auto_approved",
                metadata_json={"order_id": order.id, "quote_id": quote.id},
            )
        self.db.add(audit)

        try:
            await self.db.flush()
        except IntegrityError as ie:
            logger.error(f"[Concurrency] Unique constraint violation on quote_id {quote_id}: {ie}")
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate order creation prevented by database unique constraint.",
            )

        logger.info(
            f"[OrderService] Created order {order.id} (status: {order.status}) for quote {quote.id}"
        )
        return order

    async def approve_order(self, order_id: str, approver: str = "human_admin") -> Order:
        """Approve an order in pending_approval status, moving it to created."""
        order = await self.get_order_by_id(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )

        if order.status != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order '{order_id}' is not in 'pending_approval' state (current: '{order.status}').",
            )

        order.status = "created"
        meta = dict(order.metadata_json or {})
        meta["approval_status"] = "human_approved"
        meta["approved_at"] = utcnow().isoformat()
        meta["approved_by"] = approver
        order.metadata_json = meta

        audit = AuditLog(
            session_id=order.session_id,
            actor=approver,
            action="order_human_approved",
            reason=f"Human operator approved order {order.id} for ₹{order.amount:,.2f}",
            amount=order.amount,
            approval_status="approved",
            metadata_json={"order_id": order.id, "approved_by": approver},
        )
        self.db.add(audit)
        await self.db.flush()
        logger.info(f"[OrderService] Order {order.id} approved by {approver}.")
        return order

    async def reject_order(
        self, order_id: str, reason: str = "Rejected by human operator", rejecter: str = "human_admin"
    ) -> Order:
        """Reject an order in pending_approval status, cancelling it."""
        order = await self.get_order_by_id(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )

        if order.status != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order '{order_id}' is not in 'pending_approval' state (current: '{order.status}').",
            )

        order.status = "cancelled"
        order.failure_reason = reason
        meta = dict(order.metadata_json or {})
        meta["approval_status"] = "human_rejected"
        meta["rejected_at"] = utcnow().isoformat()
        meta["rejected_by"] = rejecter
        meta["rejection_reason"] = reason
        order.metadata_json = meta

        audit = AuditLog(
            session_id=order.session_id,
            actor=rejecter,
            action="order_human_rejected",
            reason=f"Human operator rejected order {order.id}: {reason}",
            amount=order.amount,
            approval_status="rejected",
            metadata_json={"order_id": order.id, "reason": reason, "rejected_by": rejecter},
        )
        self.db.add(audit)
        await self.db.flush()
        logger.info(f"[OrderService] Order {order.id} rejected by {rejecter}: {reason}")
        return order

    async def list_pending_approvals(self, limit: int = 50) -> List[Order]:
        """List orders awaiting human approval."""
        query = (
            select(Order)
            .where(Order.status == "pending_approval")
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Fetch order with relationships."""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self, user_id: Optional[str] = None, limit: int = 50
    ) -> List[Order]:
        """List orders optionally filtered by user."""
        query = select(Order).order_by(Order.created_at.desc()).limit(limit)
        if user_id:
            query = query.where(Order.buyer_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def enrich_order(self, order: Order) -> Dict[str, Any]:
        """Enrich order object with merchant and product names."""
        product_name = "Unknown Product"
        merchant_name = "Unknown Merchant"

        if order.product_id:
            prod = (
                await self.db.execute(select(Product).where(Product.id == order.product_id))
            ).scalar_one_or_none()
            if prod:
                product_name = prod.name

        if order.merchant_id:
            merch = (
                await self.db.execute(select(Merchant).where(Merchant.id == order.merchant_id))
            ).scalar_one_or_none()
            if merch:
                merchant_name = merch.name

        payment_result = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id, Payment.status == "success")
        )
        successful_payment = payment_result.scalars().first()

        return {
            "id": order.id,
            "buyer_id": order.buyer_id,
            "merchant_id": order.merchant_id,
            "merchant_name": merchant_name,
            "product_id": order.product_id,
            "product_name": product_name,
            "quote_id": order.quote_id,
            "session_id": order.session_id,
            "amount": order.amount,
            "currency": order.currency,
            "status": order.status,
            "razorpay_order_id": order.razorpay_order_id,
            "failure_reason": order.failure_reason,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "payment_id": successful_payment.id if successful_payment else None,
        }
