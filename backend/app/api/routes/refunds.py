"""Refund API endpoints — full lifecycle with SSE streaming."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.refund import (
    RefundCreateRequest,
    RefundNLPRequest,
    RefundApproveRequest,
    RefundRejectRequest,
    RefundResponse,
    RefundDashboardResponse,
)
from app.services.refund_service import RefundService
from app.services.sse_manager import refund_sse_manager

logger = logging.getLogger("agentpay.api.refunds")

router = APIRouter()


# ── Eligibility ───────────────────────────────────────────────

@router.get("/eligibility/{order_id}")
async def refund_eligibility(order_id: str, db: AsyncSession = Depends(get_db)):
    """Return the product refund policy and current eligibility decision with per-check verdicts."""
    return await RefundService(db).get_eligibility(order_id)


# ── Dashboard ─────────────────────────────────────────────────

@router.get("/dashboard")
async def refund_dashboard(db: AsyncSession = Depends(get_db)):
    """Get merchant refund dashboard with aggregates and recent refunds."""
    return await RefundService(db).get_dashboard()


# ── SSE Stream ────────────────────────────────────────────────

@router.get("/stream/{refund_id}")
async def refund_stream(refund_id: str):
    """Server-Sent Events stream for real-time refund status updates."""
    return StreamingResponse(
        refund_sse_manager.event_stream(refund_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── NLP Refund Request ────────────────────────────────────────

@router.post("/request")
async def request_refund_nlp(
    body: RefundNLPRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Submit a natural-language refund request.

    The AI Buyer Agent extracts structured data, then the refund pipeline runs:
    eligibility check → AI merchant recommendation → pending approval.
    """
    from app.agents.refund_buyer_agent import RefundBuyerAgent

    # 1. AI Buyer Agent extraction
    agent = RefundBuyerAgent()
    extraction, used_fallback, provider = await agent.extract_refund_request(body.message)

    # Use explicitly provided order_id if extraction didn't find one
    order_id = extraction.order_id or body.order_id
    if not order_id:
        return {
            "extraction": extraction.model_dump(),
            "used_fallback": used_fallback,
            "provider": provider,
            "eligibility": None,
            "refund": None,
            "error": "Could not determine order ID. Please provide the order ID.",
        }

    # 2. Generate idempotency key if not provided
    if not idempotency_key or len(idempotency_key.strip()) < 8:
        import uuid
        idempotency_key = f"nlp-refund-{uuid.uuid4()}"

    # 3. Run refund pipeline
    service = RefundService(db)
    try:
        eligibility = await service.get_eligibility(order_id, buyer_id=body.user_id)
        refund_result = await service.request_refund(
            order_id=order_id,
            payment_id=None,
            amount=extraction.requested_amount,
            reason=extraction.reason,
            idempotency_key=idempotency_key.strip(),
            buyer_id=body.user_id,
            reason_category=extraction.reason_category,
            refund_type=extraction.refund_type,
        )
        return {
            "extraction": extraction.model_dump(),
            "used_fallback": used_fallback,
            "provider": provider,
            "eligibility": eligibility,
            "refund": refund_result,
        }
    except HTTPException as e:
        eligibility = await service.get_eligibility(order_id, buyer_id=body.user_id)
        return {
            "extraction": extraction.model_dump(),
            "used_fallback": used_fallback,
            "provider": provider,
            "eligibility": eligibility,
            "refund": None,
            "error": e.detail,
        }


# ── Direct Refund Request ─────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_refund(
    body: RefundCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Create a refund request directly with structured fields."""
    if not idempotency_key or len(idempotency_key.strip()) < 8:
        raise HTTPException(status_code=400, detail="A valid Idempotency-Key header is required (min 8 chars).")
    return await RefundService(db).request_refund(
        order_id=body.order_id,
        payment_id=body.payment_id,
        amount=body.amount,
        reason=body.reason,
        idempotency_key=idempotency_key.strip(),
    )


# ── Refund by ID ──────────────────────────────────────────────

@router.get("/{refund_id}")
async def get_refund(refund_id: str, db: AsyncSession = Depends(get_db)):
    """Get refund details with full event timeline."""
    result = await RefundService(db).get_refund(refund_id)
    if not result:
        raise HTTPException(status_code=404, detail="Refund not found.")
    return result


# ── Approve / Reject / Retry ─────────────────────────────────

@router.post("/{refund_id}/approve")
async def approve_refund(
    refund_id: str,
    body: Optional[RefundApproveRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Merchant approves a refund. Optionally set a partial amount."""
    approved_amount = body.approved_amount if body else None
    merchant_note = body.merchant_note if body else None
    return await RefundService(db).approve_refund(
        refund_id=refund_id,
        approved_amount=approved_amount,
        merchant_note=merchant_note,
    )


@router.post("/{refund_id}/reject")
async def reject_refund(
    refund_id: str,
    body: RefundRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Merchant rejects a refund."""
    return await RefundService(db).reject_refund(
        refund_id=refund_id,
        rejection_reason=body.rejection_reason,
    )


@router.post("/{refund_id}/retry")
async def retry_refund(refund_id: str, db: AsyncSession = Depends(get_db)):
    """Retry a failed refund."""
    return await RefundService(db).retry_refund(refund_id)


# ── Order Refunds ─────────────────────────────────────────────

@router.get("/order/{order_id}")
async def get_order_refunds(order_id: str, db: AsyncSession = Depends(get_db)):
    """List all refunds for a specific order."""
    refunds = await RefundService(db).get_order_refunds(order_id)
    return {"order_id": order_id, "refunds": refunds, "count": len(refunds)}
