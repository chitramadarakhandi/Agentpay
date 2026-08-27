"""Payment routes — with Rate Limiting, Idempotency, HMAC Webhook Verification, and Dual Convergence."""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from app.services.payment_service import PaymentService
from app.services.idempotency_service import IdempotencyService
from app.core.rate_limiter import limit_payment_create, limit_payment_verify
from app.core.security import verify_webhook_signature
from app.core.config import get_settings
from app.payments.razorpay_service import RazorpayService

logger = logging.getLogger("agentpay.api.payments")
settings = get_settings()
router = APIRouter()


@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    dependencies=[Depends(limit_payment_create)],
)
async def create_payment(
    body: PaymentCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay payment order.
    
    Protected by Token Bucket Rate Limiter (5 burst / 0.5 req/s)
    and distributed Idempotency with 24-hour TTL.
    """
    idemp_svc = IdempotencyService(db)
    if idempotency_key:
        cached = await idemp_svc.check_and_start(
            idempotency_key=idempotency_key,
            endpoint="/api/payments/create",
            payload=body.model_dump(),
        )
        if cached:
            _, response_data = cached
            return response_data

    payment_svc = PaymentService(db)
    try:
        result = await payment_svc.create_payment_intent(order_id=body.order_id)
        if idempotency_key:
            await idemp_svc.complete(
                idempotency_key=idempotency_key,
                response_code=status.HTTP_200_OK,
                response_body=result,
            )
        return result
    except Exception as exc:
        if idempotency_key:
            await idemp_svc.fail(idempotency_key)
        raise exc


@router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    dependencies=[Depends(limit_payment_verify)],
)
async def verify_payment(
    body: PaymentVerifyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Client-driven payment signature verification.
    
    Verifies HMAC-SHA256 signature server-side and converges order state.
    Safe to execute even if the webhook arrives before or simultaneously.
    """
    idemp_svc = IdempotencyService(db)
    if idempotency_key:
        cached = await idemp_svc.check_and_start(
            idempotency_key=idempotency_key,
            endpoint="/api/payments/verify",
            payload=body.model_dump(),
        )
        if cached:
            _, response_data = cached
            return response_data

    payment_svc = PaymentService(db)
    rzp_svc = RazorpayService()

    try:
        # Verify signature
        is_valid = rzp_svc.verify_payment(
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )

        if not is_valid:
            logger.warning(
                f"[PaymentVerify] Invalid signature received for order {body.order_id}"
            )
            # Record failure
            await payment_svc.process_payment_failure(
                order_id=body.order_id,
                reason="Invalid cryptographic signature",
                source="client_verify",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed.",
            )

        # Signature is valid -> converge state to success
        result = await payment_svc.process_payment_success(
            order_id=body.order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
            source="client_verify",
        )

        if idempotency_key:
            await idemp_svc.complete(
                idempotency_key=idempotency_key,
                response_code=status.HTTP_200_OK,
                response_body=result,
            )
        return result
    except Exception as exc:
        if idempotency_key:
            await idemp_svc.fail(idempotency_key)
        raise exc


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Razorpay Server-to-Server Webhook Handler.
    
    1. Validates HMAC SHA-256 signature using webhook secret.
    2. Handles events: 'payment.captured', 'order.paid', 'payment.failed'.
    3. Dual convergence: safely reconciles state idempotently even if client-verify also fired.
    """
    raw_body = await request.body()

    # Verify signature if secret is configured or header is present
    webhook_secret = settings.razorpay_webhook_secret or settings.razorpay_key_secret
    if webhook_secret and x_razorpay_signature:
        # Check signature
        valid = verify_webhook_signature(
            body=raw_body,
            signature=x_razorpay_signature,
            secret=webhook_secret,
        )
        if not valid:
            logger.error("[Webhook] Invalid webhook signature rejected.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature.",
            )
    else:
        logger.info("[Webhook] Test mode webhook processed (no secret/header check required).")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"[Webhook] Failed to parse JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event = event_data.get("event", "")
    payload = event_data.get("payload", {})
    payment_svc = PaymentService(db)

    logger.info(f"[Webhook] Processing Razorpay webhook event: '{event}'")

    if event in ("payment.captured", "order.paid"):
        payment_entity = payload.get("payment", {}).get("entity", {})
        order_entity = payload.get("order", {}).get("entity", {})
        
        razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")
        razorpay_payment_id = payment_entity.get("id", f"pay_wh_{event_data.get('created_at', '0')}")
        notes = payment_entity.get("notes", {}) or order_entity.get("notes", {})
        order_id = notes.get("order_id") or razorpay_order_id

        if not order_id:
            logger.warning("[Webhook] No order_id found in webhook payload notes or entity.")
            return {"status": "skipped", "reason": "no_order_id"}

        result = await payment_svc.process_payment_success(
            order_id=order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=x_razorpay_signature or "webhook_verified",
            source="razorpay_webhook",
        )
        return {"status": "processed", "event": event, "result": result}

    elif event == "payment.failed":
        payment_entity = payload.get("payment", {}).get("entity", {})
        razorpay_order_id = payment_entity.get("order_id")
        error_desc = payment_entity.get("error_description", "Payment failed at gateway")
        notes = payment_entity.get("notes", {})
        order_id = notes.get("order_id") or razorpay_order_id

        if order_id:
            result = await payment_svc.process_payment_failure(
                order_id=order_id,
                reason=error_desc,
                source="razorpay_webhook",
            )
            return {"status": "processed", "event": event, "result": result}

    return {"status": "received", "event": event}
