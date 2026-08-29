"""Subscription Service — Agent AutoPay with e-Mandate governance.

Handles subscription lifecycle: create, charge, pause, cancel.
All operations are deterministic and write immutable audit trails.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.subscription import Subscription, SubscriptionCharge
from app.models.user import BuyerProfile
from app.models.audit import AuditLog

logger = logging.getLogger("agentpay.subscription_service")


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_subscription(
        self,
        user_id: str,
        plan_name: str,
        amount_per_cycle: float,
        cycle: str = "monthly",
        max_cycles: int = 12,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a new agent subscription with mandate validation.

        Validates against buyer's spending passport before activating.
        """
        # Validate against spending passport
        profile_res = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        single_limit = profile.single_transaction_limit if profile else 80000.0
        daily_limit = profile.daily_spending_limit if profile else 150000.0

        if amount_per_cycle > single_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription amount ₹{amount_per_cycle:,.2f} exceeds single transaction limit ₹{single_limit:,.2f}.",
            )

        sub_id = str(uuid.uuid4())
        mandate_id = f"mandate_test_{uuid.uuid4().hex[:14]}"
        rzp_sub_id = f"sub_test_{uuid.uuid4().hex[:14]}"

        subscription = Subscription(
            id=sub_id,
            user_id=user_id,
            plan_name=plan_name,
            description=description,
            amount_per_cycle=amount_per_cycle,
            cycle=cycle,
            max_cycles=max_cycles,
            mandate_id=mandate_id,
            razorpay_subscription_id=rzp_sub_id,
            status="active",
        )
        self.db.add(subscription)

        # Audit trail
        self.db.add(AuditLog(
            session_id=f"sub-{sub_id[:8]}",
            actor="subscription_service",
            action="subscription_created",
            reason=f"Agent AutoPay subscription '{plan_name}' created at ₹{amount_per_cycle:,.2f}/{cycle}. Mandate: {mandate_id}",
            amount=amount_per_cycle,
            approval_status="approved",
            metadata_json={
                "subscription_id": sub_id,
                "mandate_id": mandate_id,
                "cycle": cycle,
                "max_cycles": max_cycles,
            },
        ))

        await self.db.flush()
        logger.info(f"[SubscriptionService] Created subscription {sub_id} for user {user_id}")
        return self._serialize(subscription)

    async def charge_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Execute the next recurring charge for a subscription.

        Simulates Razorpay recurring payment in test mode.
        """
        sub = await self._get_subscription(subscription_id)

        if sub.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription is '{sub.status}', not active. Cannot charge.",
            )

        if sub.current_cycle >= sub.max_cycles:
            sub.status = "completed"
            await self.db.flush()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription has completed all {sub.max_cycles} cycles.",
            )

        # Create charge
        next_cycle = sub.current_cycle + 1
        charge_id = str(uuid.uuid4())
        rzp_payment_id = f"pay_sub_{uuid.uuid4().hex[:12]}"

        charge = SubscriptionCharge(
            id=charge_id,
            subscription_id=sub.id,
            cycle_number=next_cycle,
            amount=sub.amount_per_cycle,
            status="success",
            razorpay_payment_id=rzp_payment_id,
        )
        self.db.add(charge)

        # Update subscription
        sub.current_cycle = next_cycle
        sub.total_charged = round(sub.total_charged + sub.amount_per_cycle, 2)
        if next_cycle >= sub.max_cycles:
            sub.status = "completed"
        else:
            cycle_days = 30 if sub.cycle == "monthly" else 7
            sub.next_charge_at = datetime.now(timezone.utc) + timedelta(days=cycle_days)

        # Audit trail
        self.db.add(AuditLog(
            session_id=f"sub-{sub.id[:8]}",
            actor="subscription_service",
            action="subscription_charged",
            reason=f"Cycle {next_cycle}/{sub.max_cycles} charged ₹{sub.amount_per_cycle:,.2f} via Razorpay mandate.",
            amount=sub.amount_per_cycle,
            approval_status="approved",
            metadata_json={
                "subscription_id": sub.id,
                "cycle": next_cycle,
                "razorpay_payment_id": rzp_payment_id,
                "total_charged": sub.total_charged,
            },
        ))

        await self.db.flush()
        logger.info(f"[SubscriptionService] Charged cycle {next_cycle} for subscription {sub.id}")

        return {
            "charge_id": charge.id,
            "subscription_id": sub.id,
            "cycle_number": next_cycle,
            "amount": charge.amount,
            "status": charge.status,
            "razorpay_payment_id": rzp_payment_id,
            "subscription_status": sub.status,
            "total_charged": sub.total_charged,
            "remaining_cycles": max(0, sub.max_cycles - next_cycle),
        }

    async def pause_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Pause an active subscription."""
        sub = await self._get_subscription(subscription_id)
        if not sub.can_transition_to("paused"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pause subscription in '{sub.status}' state.",
            )
        sub.status = "paused"

        self.db.add(AuditLog(
            session_id=f"sub-{sub.id[:8]}",
            actor="subscription_service",
            action="subscription_paused",
            reason=f"Agent AutoPay '{sub.plan_name}' paused by user after {sub.current_cycle} cycles.",
            amount=sub.amount_per_cycle,
            approval_status="approved",
            metadata_json={"subscription_id": sub.id},
        ))

        await self.db.flush()
        return self._serialize(sub)

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Resume a paused subscription."""
        sub = await self._get_subscription(subscription_id)
        if not sub.can_transition_to("active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume subscription in '{sub.status}' state.",
            )
        sub.status = "active"
        cycle_days = 30 if sub.cycle == "monthly" else 7
        sub.next_charge_at = datetime.now(timezone.utc) + timedelta(days=cycle_days)

        self.db.add(AuditLog(
            session_id=f"sub-{sub.id[:8]}",
            actor="subscription_service",
            action="subscription_resumed",
            reason=f"Agent AutoPay '{sub.plan_name}' resumed. Next charge: {sub.next_charge_at.isoformat()}",
            amount=sub.amount_per_cycle,
            approval_status="approved",
            metadata_json={"subscription_id": sub.id},
        ))

        await self.db.flush()
        return self._serialize(sub)

    async def cancel_subscription(self, subscription_id: str, reason: str = "User cancelled") -> Dict[str, Any]:
        """Cancel a subscription permanently."""
        sub = await self._get_subscription(subscription_id)
        if not sub.can_transition_to("cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel subscription in '{sub.status}' state.",
            )
        sub.status = "cancelled"

        self.db.add(AuditLog(
            session_id=f"sub-{sub.id[:8]}",
            actor="subscription_service",
            action="subscription_cancelled",
            reason=f"Agent AutoPay '{sub.plan_name}' cancelled: {reason}. Total charged: ₹{sub.total_charged:,.2f} over {sub.current_cycle} cycles.",
            amount=sub.total_charged,
            approval_status="approved",
            metadata_json={"subscription_id": sub.id, "reason": reason},
        ))

        await self.db.flush()
        return self._serialize(sub)

    async def get_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """List all subscriptions for a user."""
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        return [self._serialize(s) for s in result.scalars().all()]

    async def get_subscription_detail(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription with charge history."""
        sub = await self._get_subscription(subscription_id)
        data = self._serialize(sub)
        data["charges"] = [
            {
                "id": c.id,
                "cycle_number": c.cycle_number,
                "amount": c.amount,
                "status": c.status,
                "razorpay_payment_id": c.razorpay_payment_id,
                "failure_reason": c.failure_reason,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in sorted(sub.charges, key=lambda x: x.cycle_number)
        ]
        return data

    async def _get_subscription(self, subscription_id: str) -> Subscription:
        result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription '{subscription_id}' not found.",
            )
        return sub

    def _serialize(self, sub: Subscription) -> Dict[str, Any]:
        return {
            "id": sub.id,
            "user_id": sub.user_id,
            "plan_name": sub.plan_name,
            "description": sub.description,
            "amount_per_cycle": sub.amount_per_cycle,
            "currency": sub.currency,
            "cycle": sub.cycle,
            "max_cycles": sub.max_cycles,
            "current_cycle": sub.current_cycle,
            "status": sub.status,
            "mandate_id": sub.mandate_id,
            "razorpay_subscription_id": sub.razorpay_subscription_id,
            "next_charge_at": sub.next_charge_at.isoformat() if sub.next_charge_at else None,
            "total_charged": sub.total_charged,
            "remaining_cycles": max(0, sub.max_cycles - sub.current_cycle),
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
        }
