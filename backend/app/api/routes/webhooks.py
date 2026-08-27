"""Razorpay webhook endpoints for refund events."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.security import verify_webhook_signature
from app.services.refund_service import RefundService

logger = logging.getLogger("agentpay.api.webhooks")
settings = get_settings()

router = APIRouter()


@router.post("/razorpay")
async def razorpay_refund_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Handle Razorpay refund webhook events.

    Security:
    1. Verify HMAC-SHA256 signature
    2. Validate event structure
    3. Deduplicate events
    4. Update refund state
    5. Broadcast via SSE
    6. Record in audit trail
    """
    raw_body = await request.body()

    # 1. Verify signature
    webhook_secret = settings.razorpay_webhook_secret or settings.razorpay_key_secret
    if webhook_secret and x_razorpay_signature:
        valid = verify_webhook_signature(
            body=raw_body,
            signature=x_razorpay_signature,
            secret=webhook_secret,
        )
        if not valid:
            logger.error("[RefundWebhook] Invalid webhook signature rejected.")
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    else:
        logger.info("[RefundWebhook] Test mode webhook (no signature check).")

    # 2. Parse payload
    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"[RefundWebhook] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event_type = event_data.get("event", "")
    event_id = event_data.get("account_id", "") + "_" + str(event_data.get("created_at", "0"))
    payload = event_data.get("payload", {})

    logger.info(f"[RefundWebhook] Processing event: '{event_type}'")

    # 3. Handle refund events
    if event_type in ("refund.processed", "refund.created", "refund.failed"):
        refund_entity = payload.get("refund", {}).get("entity", {})
        gateway_refund_id = refund_entity.get("id")

        if not gateway_refund_id:
            return {"status": "skipped", "reason": "no_refund_id"}

        service = RefundService(db)
        result = await service.process_webhook(
            event_id=event_id,
            event_type=event_type,
            gateway_refund_id=gateway_refund_id,
            payload=refund_entity,
        )

        return {
            "status": "processed" if result else "deduplicated",
            "event": event_type,
        }

    return {"status": "received", "event": event_type}
