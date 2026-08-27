"""Security utilities."""

import hashlib
import hmac


def verify_razorpay_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    secret: str,
) -> bool:
    """Verify Razorpay payment signature using HMAC-SHA256.
    
    This is a critical security check — never trust frontend payment 
    success alone. Always verify server-side.
    """
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(
    body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify Razorpay webhook signature."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
