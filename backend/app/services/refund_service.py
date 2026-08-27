"""Secure refund orchestration with full lifecycle, policy engine, AI agents, SSE, and audit.

Refund flow:
  AI Proposal → Deterministic Policy → Authorization → Refund Service → Razorpay

The AI may understand and classify the request, but NEVER directly executes a refund.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_middleware import get_current_request_id
from app.models.audit import AuditLog
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.refund import Refund, ACTIVE_STATES
from app.models.refund_event import RefundEvent, WebhookEvent
from app.payments.razorpay_service import RazorpayService
from app.services.refund_policy import (
    evaluate_refund_eligibility,
    get_refund_policy,
    refund_deadline,
    requires_merchant_approval,
)
from app.services.sse_manager import refund_sse_manager

logger = logging.getLogger("agentpay.refund_service")


class RefundService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gateway = RazorpayService()

    # ── Internal helpers ──────────────────────────────────────

    async def _record_event(
        self,
        refund: Refund,
        event_type: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> RefundEvent:
        """Record an immutable event in the refund timeline."""
        event = RefundEvent(
            refund_id=refund.id,
            event_type=event_type,
            actor=actor,
            status=refund.status,
            metadata_json=metadata or {},
        )
        self.db.add(event)
        await self.db.flush()

        # Push SSE update
        await refund_sse_manager.publish(refund.id, event_type, {
            "status": refund.status,
            "event_type": event_type,
            "actor": actor,
            "metadata": metadata or {},
        })

        return event

    async def _audit(
        self,
        session_id: str,
        action: str,
        reason: str,
        refund: Refund | None = None,
        status_name: str = "approved",
    ):
        """Record an audit log entry."""
        self.db.add(AuditLog(
            session_id=session_id,
            actor="refund_service",
            action=action,
            reason=reason,
            amount=refund.effective_amount if refund else None,
            approval_status=status_name,
            metadata_json={
                "order_id": refund.order_id if refund else None,
                "payment_id": refund.payment_id if refund else None,
                "refund_id": refund.id if refund else None,
                "request_id": get_current_request_id(),
            },
        ))
        await self.db.flush()

    def _transition(self, refund: Refund, new_status: str):
        """Enforce state machine transition."""
        if not refund.can_transition_to(new_status):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state transition: {refund.status} → {new_status}",
            )
        refund.status = new_status

    async def _refunded_total(self, payment_id: str) -> float:
        """Sum of all completed refunds for a payment."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Refund.amount), 0.0)).where(
                Refund.payment_id == payment_id, Refund.status == "processed"
            )
        )
        return float(result.scalar_one())

    async def _active_refund_for_order(self, order_id: str) -> Refund | None:
        """Check if there's already an active (non-terminal) refund for this order."""
        result = await self.db.execute(
            select(Refund).where(
                Refund.order_id == order_id,
                Refund.status.in_(ACTIVE_STATES),
            )
        )
        return result.scalar_one_or_none()

    async def serialize(self, refund: Refund) -> dict[str, Any]:
        """Serialize a refund with computed totals and events."""
        refunded = await self._refunded_total(refund.payment_id)
        
        # Safely fetch payment amount
        payment_amount = refund.amount
        if refund.payment_id:
            pay_res = await self.db.execute(select(Payment.amount).where(Payment.id == refund.payment_id))
            p_amount = pay_res.scalar_one_or_none()
            if p_amount is not None:
                payment_amount = p_amount

        # Events query
        ev_res = await self.db.execute(
            select(RefundEvent).where(RefundEvent.refund_id == refund.id).order_by(RefundEvent.created_at)
        )
        events = ev_res.scalars().all()

        return {
            "id": refund.id,
            "order_id": refund.order_id,
            "payment_id": refund.payment_id,
            "buyer_id": refund.buyer_id,
            "merchant_id": refund.merchant_id,
            "amount": refund.amount,
            "approved_amount": refund.approved_amount,
            "currency": refund.currency,
            "reason": refund.reason,
            "refund_type": refund.refund_type,
            "status": refund.status,
            "gateway_refund_id": refund.gateway_refund_id,
            "failure_reason": refund.failure_reason,
            "policy_result": refund.policy_result,
            "ai_recommendation": refund.ai_recommendation,
            "refunded_amount": refunded,
            "remaining_refundable_amount": max(0.0, payment_amount - refunded),
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "status": e.status,
                    "metadata": e.metadata_json,
                    "created_at": e.created_at,
                }
                for e in events
            ],
            "created_at": refund.created_at,
            "updated_at": refund.updated_at,
        }

    # ── Core refund operations ────────────────────────────────

    async def request_refund(
        self,
        order_id: str,
        payment_id: str | None,
        amount: float | None,
        reason: str,
        idempotency_key: str,
        buyer_id: str | None = None,
        reason_category: str = "other",
        refund_type: str = "full",
    ) -> dict:
        """Create a refund request and run through the eligibility pipeline.

        Flow: requested → eligibility_check → pending_approval
        """
        # 1. Idempotency check
        existing_result = await self.db.execute(
            select(Refund).where(Refund.idempotency_key == idempotency_key)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return await self.serialize(existing)

        # 2. Load order
        order = (await self.db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        # 3. Load payment
        payment_query = select(Payment).where(Payment.order_id == order_id, Payment.status == "success")
        if payment_id:
            payment_query = payment_query.where(Payment.id == payment_id)
        payment = (await self.db.execute(payment_query)).scalars().first()

        # 4. Load product
        product = None
        if order.product_id:
            product = (await self.db.execute(select(Product).where(Product.id == order.product_id))).scalar_one_or_none()

        # 5. Check for active refund
        active_refund = await self._active_refund_for_order(order_id)

        # 6. Calculate totals
        refunded_total = await self._refunded_total(payment.id) if payment else 0.0
        remaining = round(payment.amount - refunded_total, 2) if payment else 0.0
        requested = amount if amount is not None else remaining

        # 7. Run policy engine
        eligibility = evaluate_refund_eligibility(
            order=order,
            payment=payment,
            product=product,
            refunded_total=refunded_total,
            requested_amount=amount,
            active_refund_exists=active_refund is not None,
            buyer_id=buyer_id,
        )
        policy_result = eligibility.to_dict()

        if not eligibility.eligible:
            raise HTTPException(status_code=400, detail=policy_result["decision_reason"])

        # 8. Validate amount
        if requested <= 0 or requested > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Refund amount must be between 0 and ₹{remaining:,.2f}."
            )

        # 9. Determine refund type
        if amount is not None and amount < remaining:
            refund_type = "partial"

        # 10. Create refund record
        refund = Refund(
            order_id=order.id,
            payment_id=payment.id,
            buyer_id=order.buyer_id,
            merchant_id=order.merchant_id,
            amount=requested,
            currency=payment.currency,
            reason=reason,
            refund_type=refund_type,
            status="requested",
            idempotency_key=idempotency_key,
            policy_result=policy_result,
        )
        self.db.add(refund)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            existing = (await self.db.execute(
                select(Refund).where(Refund.idempotency_key == idempotency_key)
            )).scalar_one()
            return await self.serialize(existing)

        # 11. Record events and transition through states
        await self._record_event(refund, "refund_requested", "buyer_agent", {
            "reason": reason,
            "reason_category": reason_category,
            "requested_amount": requested,
            "refund_type": refund_type,
        })
        await self._audit(order.session_id, "refund_requested",
                         f"Refund requested: ₹{requested:,.2f} {payment.currency}.", refund, "pending")

        # Transition: requested → eligibility_check
        self._transition(refund, "eligibility_check")
        await self._record_event(refund, "eligibility_checked", "policy_engine", policy_result)
        await self._audit(order.session_id, "refund_eligibility_checked",
                         "Payment, order, and refundable balance validated.", refund, "approved")

        # Run merchant agent recommendation
        from app.agents.refund_merchant_agent import RefundMerchantAgent
        merchant_agent = RefundMerchantAgent()
        recommendation, used_fallback, provider = await merchant_agent.recommend(
            refund_reason=reason,
            reason_category=reason_category,
            requested_amount=requested,
            policy_result=policy_result,
            product_name=product.name if product else "Unknown",
            product_category=product.category if product else "general",
        )
        refund.ai_recommendation = {
            "recommendation": recommendation.recommendation,
            "approved_amount": recommendation.approved_amount,
            "reasoning": recommendation.reasoning,
            "confidence": recommendation.confidence,
            "provider": provider,
            "used_fallback": used_fallback,
        }

        await self._record_event(refund, "merchant_recommended", "merchant_agent", refund.ai_recommendation)
        await self._audit(order.session_id, "refund_merchant_recommended",
                         f"Merchant Agent recommends: {recommendation.recommendation}.", refund, "pending")

        # Transition: eligibility_check → pending_approval
        self._transition(refund, "pending_approval")
        await self._record_event(refund, "approval_pending", "system", {
            "requires_merchant_approval": requires_merchant_approval(requested),
            "high_value": requested >= 50000,
        })

        await self.db.flush()
        return await self.serialize(refund)

    async def approve_refund(
        self,
        refund_id: str,
        approved_amount: float | None = None,
        merchant_note: str | None = None,
    ) -> dict:
        """Merchant approves a refund. Triggers Razorpay refund."""
        refund = (await self.db.execute(select(Refund).where(Refund.id == refund_id))).scalar_one_or_none()
        if not refund:
            raise HTTPException(status_code=404, detail="Refund not found.")

        if refund.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail=f"Refund must be in pending_approval state to approve. Current: {refund.status}."
            )

        order = (await self.db.execute(select(Order).where(Order.id == refund.order_id))).scalar_one()

        # Set approved amount
        if approved_amount is not None:
            if approved_amount <= 0 or approved_amount > refund.amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Approved amount must be between 0 and ₹{refund.amount:,.2f}."
                )
            refund.approved_amount = approved_amount
            if approved_amount < refund.amount:
                refund.refund_type = "partial"
        else:
            refund.approved_amount = refund.amount

        # Transition: pending_approval → approved
        self._transition(refund, "approved")
        await self._record_event(refund, "refund_approved", "merchant", {
            "approved_amount": refund.approved_amount,
            "merchant_note": merchant_note,
        })
        await self._audit(order.session_id, "refund_approved",
                         f"Merchant approved refund of ₹{refund.approved_amount:,.2f}.", refund, "approved")

        # Transition: approved → processing
        self._transition(refund, "processing")
        await self._record_event(refund, "refund_processing", "refund_service", {
            "gateway": "razorpay",
        })
        await self._audit(order.session_id, "refund_processing",
                         "Refund submitted to payment gateway.", refund)

        # Call Razorpay
        try:
            payment = (await self.db.execute(select(Payment).where(Payment.id == refund.payment_id))).scalar_one()
            gateway_result = self.gateway.create_refund(payment.razorpay_payment_id, refund.approved_amount)
            refund.gateway_refund_id = gateway_result["id"]

            # If simulated or instant success, mark as processed
            if gateway_result.get("simulated") or gateway_result.get("status") == "processed":
                self._transition(refund, "processed")
                await self._record_event(refund, "refund_processed", "razorpay", gateway_result)
                await self._audit(order.session_id, "refund_completed",
                                 "Refund completed successfully.", refund)
            else:
                # Real Razorpay: wait for webhook
                await self._record_event(refund, "razorpay_initiated", "razorpay", gateway_result)

        except Exception as exc:
            self._transition(refund, "failed")
            refund.failure_reason = str(exc)
            await self._record_event(refund, "refund_failed", "refund_service", {
                "error": str(exc),
            })
            await self._audit(order.session_id, "refund_failed",
                             f"Refund failed: {exc}", refund, "rejected")
            await self.db.flush()
            raise HTTPException(status_code=502, detail="Payment gateway refund failed.") from exc

        await self.db.flush()
        return await self.serialize(refund)

    async def reject_refund(
        self,
        refund_id: str,
        rejection_reason: str,
    ) -> dict:
        """Merchant rejects a refund."""
        refund = (await self.db.execute(select(Refund).where(Refund.id == refund_id))).scalar_one_or_none()
        if not refund:
            raise HTTPException(status_code=404, detail="Refund not found.")

        if refund.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail=f"Refund must be in pending_approval state to reject. Current: {refund.status}."
            )

        order = (await self.db.execute(select(Order).where(Order.id == refund.order_id))).scalar_one()

        self._transition(refund, "rejected")
        refund.failure_reason = rejection_reason
        await self._record_event(refund, "refund_rejected", "merchant", {
            "rejection_reason": rejection_reason,
        })
        await self._audit(order.session_id, "refund_rejected",
                         f"Merchant rejected refund: {rejection_reason}", refund, "rejected")

        await self.db.flush()
        return await self.serialize(refund)

    async def retry_refund(self, refund_id: str) -> dict:
        """Retry a failed refund."""
        refund = (await self.db.execute(select(Refund).where(Refund.id == refund_id))).scalar_one_or_none()
        if not refund:
            raise HTTPException(status_code=404, detail="Refund not found.")

        if refund.status != "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Only failed refunds can be retried. Current: {refund.status}."
            )

        order = (await self.db.execute(select(Order).where(Order.id == refund.order_id))).scalar_one()

        # Transition: failed → processing
        self._transition(refund, "processing")
        refund.failure_reason = None
        await self._record_event(refund, "refund_retried", "system", {
            "previous_status": "failed",
        })
        await self._audit(order.session_id, "refund_retried",
                         "Retrying failed refund.", refund, "pending")

        # Call Razorpay again
        try:
            payment = refund.payment
            refund_amount = refund.approved_amount or refund.amount
            gateway_result = self.gateway.create_refund(payment.razorpay_payment_id, refund_amount)
            refund.gateway_refund_id = gateway_result["id"]

            if gateway_result.get("simulated") or gateway_result.get("status") == "processed":
                self._transition(refund, "processed")
                await self._record_event(refund, "refund_processed", "razorpay", gateway_result)
                await self._audit(order.session_id, "refund_completed",
                                 "Refund completed on retry.", refund)
            else:
                await self._record_event(refund, "razorpay_initiated", "razorpay", gateway_result)

        except Exception as exc:
            self._transition(refund, "failed")
            refund.failure_reason = str(exc)
            await self._record_event(refund, "refund_failed", "refund_service", {
                "error": str(exc), "retry": True,
            })
            await self._audit(order.session_id, "refund_failed",
                             f"Retry failed: {exc}", refund, "rejected")
            await self.db.flush()
            raise HTTPException(status_code=502, detail="Payment gateway refund failed on retry.") from exc

        await self.db.flush()
        return await self.serialize(refund)

    async def process_webhook(
        self,
        event_id: str,
        event_type: str,
        gateway_refund_id: str,
        payload: dict,
    ) -> dict | None:
        """Process a Razorpay refund webhook event."""
        # 1. Deduplicate webhook
        existing = (await self.db.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider == "razorpay",
                WebhookEvent.event_id == event_id,
            )
        )).scalar_one_or_none()

        if existing:
            logger.info(f"[Webhook] Duplicate webhook {event_id}, skipping.")
            return None

        # 2. Record webhook
        webhook = WebhookEvent(
            provider="razorpay",
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            processed=False,
        )
        self.db.add(webhook)
        await self.db.flush()

        # 3. Find related refund
        refund = (await self.db.execute(
            select(Refund).where(Refund.gateway_refund_id == gateway_refund_id)
        )).scalar_one_or_none()

        if not refund:
            logger.warning(f"[Webhook] No refund found for gateway ID {gateway_refund_id}")
            webhook.processed = True
            await self.db.flush()
            return None

        order = (await self.db.execute(select(Order).where(Order.id == refund.order_id))).scalar_one()

        # 4. Update refund state based on event
        if event_type in ("refund.processed", "refund.created") and refund.status == "processing":
            self._transition(refund, "processed")
            await self._record_event(refund, "webhook_confirmed", "webhook", {
                "event_type": event_type,
                "gateway_refund_id": gateway_refund_id,
            })
            await self._audit(order.session_id, "refund_webhook_confirmed",
                             "Razorpay confirmed refund processing.", refund)

        elif event_type == "refund.failed" and refund.status == "processing":
            self._transition(refund, "failed")
            refund.failure_reason = payload.get("error_description", "Razorpay refund failed")
            await self._record_event(refund, "refund_failed", "webhook", {
                "event_type": event_type,
                "error": refund.failure_reason,
            })
            await self._audit(order.session_id, "refund_webhook_failed",
                             f"Razorpay refund failed: {refund.failure_reason}", refund, "rejected")

        webhook.processed = True
        await self.db.flush()
        return await self.serialize(refund)

    # ── Query operations ──────────────────────────────────────

    async def get_eligibility(self, order_id: str, buyer_id: str | None = None) -> dict:
        """Get full eligibility evaluation with structured check verdicts."""
        order = (await self.db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        payment = None
        product = None

        if order:
            payment = (await self.db.execute(
                select(Payment).where(Payment.order_id == order.id, Payment.status == "success")
            )).scalars().first()
            if order.product_id:
                product = (await self.db.execute(
                    select(Product).where(Product.id == order.product_id)
                )).scalar_one_or_none()

        refunded = await self._refunded_total(payment.id) if payment else 0.0
        remaining = round(payment.amount - refunded, 2) if payment else 0.0
        active_refund = await self._active_refund_for_order(order_id) if order else None

        eligibility = evaluate_refund_eligibility(
            order=order,
            payment=payment,
            product=product,
            refunded_total=refunded,
            requested_amount=None,
            active_refund_exists=active_refund is not None,
            buyer_id=buyer_id,
        )

        policy = get_refund_policy(product.category if product else None)
        deadline = refund_deadline(order.created_at, policy["window_days"]) if order else None

        result = eligibility.to_dict()
        result.update({
            "order_id": order.id if order else order_id,
            "payment_id": payment.id if payment else None,
            "product_id": order.product_id if order else None,
            "product_name": product.name if product else "Unknown product",
            "category": product.category if product else "general",
            "merchant_id": order.merchant_id if order else None,
            "amount_paid": payment.amount if payment else 0,
            "refunded_amount": refunded,
            "remaining_refundable_amount": remaining,
            "currency": order.currency if order else "INR",
            "policy": {**policy, "deadline": deadline.isoformat() if deadline else None},
        })
        return result

    async def get_refund(self, refund_id: str) -> dict | None:
        """Get refund by ID with full detail."""
        refund = (await self.db.execute(select(Refund).where(Refund.id == refund_id))).scalar_one_or_none()
        return await self.serialize(refund) if refund else None

    async def get_order_refunds(self, order_id: str) -> list[dict]:
        """Get all refunds for an order."""
        result = await self.db.execute(
            select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at.desc())
        )
        refunds = result.scalars().all()
        return [await self.serialize(r) for r in refunds]

    async def get_dashboard(self) -> dict:
        """Get merchant refund dashboard aggregates."""
        all_refunds = (await self.db.execute(
            select(Refund).order_by(Refund.created_at.desc())
        )).scalars().all()

        total_refunded = sum(
            r.approved_amount or r.amount for r in all_refunds if r.status == "processed"
        )

        serialized = [await self.serialize(r) for r in all_refunds[:50]]

        return {
            "total_refunds": len(all_refunds),
            "pending_approval": sum(1 for r in all_refunds if r.status == "pending_approval"),
            "approved": sum(1 for r in all_refunds if r.status == "approved"),
            "processing": sum(1 for r in all_refunds if r.status == "processing"),
            "completed": sum(1 for r in all_refunds if r.status == "processed"),
            "rejected": sum(1 for r in all_refunds if r.status == "rejected"),
            "failed": sum(1 for r in all_refunds if r.status == "failed"),
            "total_refunded_amount": total_refunded,
            "refunds": serialized,
        }
