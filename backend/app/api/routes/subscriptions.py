"""Subscription API routes — Agent AutoPay with e-Mandate governance."""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger("agentpay.api.subscriptions")

router = APIRouter()


class SubscriptionCreateRequest(BaseModel):
    user_id: str = "demo-user-001"
    plan_name: str
    description: str = ""
    amount_per_cycle: float
    cycle: str = "monthly"  # monthly, weekly
    max_cycles: int = 12


class SubscriptionCancelRequest(BaseModel):
    reason: str = "User cancelled"


@router.post("")
async def create_subscription(
    body: SubscriptionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new Agent AutoPay subscription with Razorpay mandate.

    Validates amount against buyer spending passport before activation.
    """
    service = SubscriptionService(db)
    result = await service.create_subscription(
        user_id=body.user_id,
        plan_name=body.plan_name,
        description=body.description,
        amount_per_cycle=body.amount_per_cycle,
        cycle=body.cycle,
        max_cycles=body.max_cycles,
    )
    await db.commit()
    return result


@router.get("")
async def list_subscriptions(
    user_id: str = "demo-user-001",
    db: AsyncSession = Depends(get_db),
):
    """List all subscriptions for a user."""
    service = SubscriptionService(db)
    subs = await service.get_subscriptions(user_id)
    return {"subscriptions": subs, "count": len(subs)}


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get subscription details with charge history."""
    service = SubscriptionService(db)
    return await service.get_subscription_detail(subscription_id)


@router.post("/{subscription_id}/charge")
async def charge_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger the next recurring charge cycle for a subscription.

    Simulates Razorpay mandate-based auto-debit in test mode.
    """
    service = SubscriptionService(db)
    result = await service.charge_subscription(subscription_id)
    await db.commit()
    return result


@router.post("/{subscription_id}/pause")
async def pause_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Pause an active subscription mandate."""
    service = SubscriptionService(db)
    result = await service.pause_subscription(subscription_id)
    await db.commit()
    return result


@router.post("/{subscription_id}/resume")
async def resume_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused subscription mandate."""
    service = SubscriptionService(db)
    result = await service.resume_subscription(subscription_id)
    await db.commit()
    return result


@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    body: Optional[SubscriptionCancelRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a subscription permanently."""
    reason = body.reason if body else "User cancelled"
    service = SubscriptionService(db)
    result = await service.cancel_subscription(subscription_id, reason=reason)
    await db.commit()
    return result
