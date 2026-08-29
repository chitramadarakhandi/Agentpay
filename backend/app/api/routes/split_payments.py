"""Split Payment API routes — Razorpay Route multi-vendor settlement."""

import logging
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.split_payment_service import SplitPaymentService

logger = logging.getLogger("agentpay.api.split_payments")

router = APIRouter()


class MerchantShare(BaseModel):
    merchant_id: str
    merchant_name: str
    amount: float
    item_description: str = ""


class SplitPaymentCreateRequest(BaseModel):
    total_amount: float
    merchants: List[MerchantShare]
    platform_fee_percent: float = 5.0
    session_id: Optional[str] = None
    order_id: Optional[str] = None


@router.post("")
async def create_split_payment(
    body: SplitPaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay Route split payment across multiple merchants.

    Automatically calculates platform fee and distributes remaining amount
    proportionally to each merchant.
    """
    service = SplitPaymentService(db)
    result = await service.create_split_payment(
        total_amount=body.total_amount,
        merchants=[m.model_dump() for m in body.merchants],
        platform_fee_percent=body.platform_fee_percent,
        session_id=body.session_id,
        order_id=body.order_id,
    )
    await db.commit()
    return result


@router.get("")
async def list_split_payments(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List recent split payments."""
    service = SplitPaymentService(db)
    splits = await service.list_split_payments(limit=limit)
    return {"split_payments": splits, "count": len(splits)}


@router.get("/{split_payment_id}")
async def get_split_payment(
    split_payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get split payment details with per-merchant settlement breakdown."""
    service = SplitPaymentService(db)
    return await service.get_split_details(split_payment_id)


@router.post("/{split_payment_id}/settle")
async def settle_split_payment(
    split_payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Execute Razorpay Route transfers to settle all merchant shares.

    Simulates individual transfer calls to each merchant's connected account.
    """
    service = SplitPaymentService(db)
    result = await service.execute_settlement(split_payment_id)
    await db.commit()
    return result
