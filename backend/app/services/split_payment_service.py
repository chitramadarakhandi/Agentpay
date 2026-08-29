"""Split Payment Service — Razorpay Route multi-vendor settlement.

Handles splitting a single payment across multiple merchants with
deterministic platform fee calculation and simulated Route transfers.
"""

import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.split_payment import SplitPayment, SplitSettlement
from app.models.audit import AuditLog

logger = logging.getLogger("agentpay.split_payment_service")


class SplitPaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_split_payment(
        self,
        total_amount: float,
        merchants: List[Dict[str, Any]],
        platform_fee_percent: float = 5.0,
        session_id: str = None,
        order_id: str = None,
    ) -> Dict[str, Any]:
        """Create a multi-vendor split payment.

        Args:
            total_amount: Total payment amount
            merchants: List of dicts with keys: merchant_id, merchant_name, amount, item_description
            platform_fee_percent: Platform commission percentage
            session_id: Optional session for audit trail
            order_id: Optional existing order link
        """
        if not merchants or len(merchants) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split payment requires at least 2 merchants.",
            )

        # Calculate platform fee
        platform_fee_amount = round(total_amount * platform_fee_percent / 100, 2)
        net_merchant_amount = round(total_amount - platform_fee_amount, 2)

        # Validate merchant amounts sum to net amount
        merchant_total = sum(m.get("amount", 0) for m in merchants)
        if abs(merchant_total - net_merchant_amount) > 1.0:
            # Auto-adjust proportionally if amounts don't match
            for m in merchants:
                proportion = m["amount"] / merchant_total if merchant_total > 0 else 1.0 / len(merchants)
                m["amount"] = round(net_merchant_amount * proportion, 2)

        # Create split payment
        split = SplitPayment(
            order_id=order_id,
            session_id=session_id or f"split-{uuid.uuid4().hex[:8]}",
            total_amount=total_amount,
            platform_fee_percent=platform_fee_percent,
            platform_fee_amount=platform_fee_amount,
            net_merchant_amount=net_merchant_amount,
            status="created",
            metadata_json={
                "merchant_count": len(merchants),
                "fee_model": "percentage",
            },
        )
        self.db.add(split)
        await self.db.flush()

        # Create settlements for each merchant
        settlements = []
        for m in merchants:
            percent_share = round((m["amount"] / total_amount) * 100, 2)
            settlement = SplitSettlement(
                split_payment_id=split.id,
                merchant_id=m["merchant_id"],
                merchant_name=m["merchant_name"],
                item_description=m.get("item_description", ""),
                amount=m["amount"],
                percent_share=percent_share,
                status="pending",
            )
            self.db.add(settlement)
            settlements.append(settlement)

        # Audit trail
        self.db.add(AuditLog(
            session_id=split.session_id,
            actor="split_payment_service",
            action="split_payment_created",
            reason=(
                f"Razorpay Route split payment created: ₹{total_amount:,.2f} across {len(merchants)} merchants. "
                f"Platform fee: {platform_fee_percent}% (₹{platform_fee_amount:,.2f})"
            ),
            amount=total_amount,
            approval_status="approved",
            policy_result={
                "split_type": "razorpay_route",
                "merchant_count": len(merchants),
                "platform_fee_percent": platform_fee_percent,
                "arithmetic_breakdown": [
                    f"Total Amount: ₹{total_amount:,.2f}",
                    f"Platform Fee ({platform_fee_percent}%): ₹{platform_fee_amount:,.2f}",
                    f"Net to Merchants: ₹{net_merchant_amount:,.2f}",
                ] + [
                    f"  → {m['merchant_name']}: ₹{m['amount']:,.2f}"
                    for m in merchants
                ],
                "explainability_score": 1.0,
            },
            metadata_json={
                "split_payment_id": split.id,
                "merchants": [{"name": m["merchant_name"], "amount": m["amount"]} for m in merchants],
            },
        ))

        await self.db.flush()
        logger.info(f"[SplitPaymentService] Created split payment {split.id} across {len(merchants)} merchants")

        return self._serialize(split, settlements)

    async def execute_settlement(self, split_payment_id: str) -> Dict[str, Any]:
        """Execute simulated Razorpay Route transfers to each merchant."""
        split = await self._get_split_payment(split_payment_id)

        if split.status == "settled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split payment is already settled.",
            )

        split.status = "processing"
        now = datetime.now(timezone.utc)

        for settlement in split.settlements:
            # Simulate Razorpay Route transfer
            transfer_id = f"trf_test_{uuid.uuid4().hex[:14]}"
            settlement.razorpay_transfer_id = transfer_id
            settlement.status = "settled"
            settlement.settled_at = now

        split.status = "settled"

        # Audit trail
        self.db.add(AuditLog(
            session_id=split.session_id or f"split-{split.id[:8]}",
            actor="split_payment_service",
            action="split_settlement_executed",
            reason=f"Razorpay Route settlement executed: {len(split.settlements)} transfers completed.",
            amount=split.total_amount,
            approval_status="approved",
            metadata_json={
                "split_payment_id": split.id,
                "transfers": [
                    {
                        "merchant": s.merchant_name,
                        "amount": s.amount,
                        "transfer_id": s.razorpay_transfer_id,
                    }
                    for s in split.settlements
                ],
            },
        ))

        await self.db.flush()
        logger.info(f"[SplitPaymentService] Settled split payment {split.id}")
        return self._serialize(split, split.settlements)

    async def get_split_details(self, split_payment_id: str) -> Dict[str, Any]:
        """Get split payment details with per-merchant breakdown."""
        split = await self._get_split_payment(split_payment_id)
        return self._serialize(split, split.settlements)

    async def list_split_payments(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent split payments."""
        result = await self.db.execute(
            select(SplitPayment)
            .order_by(SplitPayment.created_at.desc())
            .limit(limit)
        )
        splits = result.scalars().all()
        return [self._serialize(s, s.settlements) for s in splits]

    async def _get_split_payment(self, split_payment_id: str) -> SplitPayment:
        result = await self.db.execute(
            select(SplitPayment).where(SplitPayment.id == split_payment_id)
        )
        split = result.scalar_one_or_none()
        if not split:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Split payment '{split_payment_id}' not found.",
            )
        return split

    def _serialize(self, split: SplitPayment, settlements: list = None) -> Dict[str, Any]:
        return {
            "id": split.id,
            "order_id": split.order_id,
            "session_id": split.session_id,
            "total_amount": split.total_amount,
            "currency": split.currency,
            "platform_fee_percent": split.platform_fee_percent,
            "platform_fee_amount": split.platform_fee_amount,
            "net_merchant_amount": split.net_merchant_amount,
            "status": split.status,
            "razorpay_order_id": split.razorpay_order_id,
            "created_at": split.created_at.isoformat() if split.created_at else None,
            "settlements": [
                {
                    "id": s.id,
                    "merchant_id": s.merchant_id,
                    "merchant_name": s.merchant_name,
                    "item_description": s.item_description,
                    "amount": s.amount,
                    "percent_share": s.percent_share,
                    "status": s.status,
                    "razorpay_transfer_id": s.razorpay_transfer_id,
                    "settled_at": s.settled_at.isoformat() if s.settled_at else None,
                }
                for s in (settlements or [])
            ],
        }
