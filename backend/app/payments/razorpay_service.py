"""Razorpay Service — Test Mode Only.

Handles order creation and server-side payment verification wrapped with Circuit Breaker.
Never exposes secret to frontend.
"""

import uuid
import logging
from typing import Optional, Dict, Any

from app.core.config import get_settings
from app.core.security import verify_razorpay_signature
from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException

settings = get_settings()
logger = logging.getLogger("agentpay.razorpay")

# Global circuit breaker instance for Razorpay client calls
razorpay_circuit_breaker = CircuitBreaker(
    name="razorpay_api",
    failure_threshold=3,
    recovery_timeout_seconds=20.0,
)


class RazorpayService:
    def __init__(self):
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        self.circuit_breaker = razorpay_circuit_breaker
        self._client = None
        if settings.razorpay_configured:
            try:
                import razorpay
                self._client = razorpay.Client(auth=(self.key_id, self.key_secret))
            except Exception as e:
                logger.error(f"[Razorpay] Client init error: {e}")

    def create_order(
        self, amount_in_rupees: float, receipt: str, notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a Razorpay test order. Amount converted to paise.
        Protected by Circuit Breaker.
        """
        amount_in_paise = int(round(amount_in_rupees * 100))

        if self._client:
            def _api_call():
                data = {
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "receipt": receipt,
                    "notes": notes or {},
                    "payment_capture": 1,
                }
                order = self._client.order.create(data=data)
                return {
                    "razorpay_order_id": order["id"],
                    "amount": order["amount"],
                    "currency": order["currency"],
                    "status": order["status"],
                }

            try:
                return self.circuit_breaker.call(_api_call)
            except CircuitBreakerOpenException as cbe:
                logger.warning(f"[Razorpay] Fast-failing via Circuit Breaker: {cbe}. Falling back to simulation mode.")
            except Exception as e:
                logger.error(f"[Razorpay] Real API error: {e}. Falling back to simulation mode.")

        # Fallback simulation mode for testing when live test keys are not yet input or circuit is open
        simulated_order_id = f"order_test_{uuid.uuid4().hex[:14]}"
        return {
            "razorpay_order_id": simulated_order_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "status": "created",
            "simulated": True,
        }

    def fetch_order(self, razorpay_order_id: str) -> Optional[Dict[str, Any]]:
        """Fetch order from Razorpay to verify status during reconciliation."""
        if not razorpay_order_id or razorpay_order_id.startswith("order_test_"):
            return {
                "id": razorpay_order_id,
                "status": "paid",
                "amount": 0,
                "simulated": True,
            }

        if self._client:
            try:
                def _fetch():
                    return self._client.order.fetch(razorpay_order_id)
                return self.circuit_breaker.call(_fetch)
            except Exception as exc:
                logger.error(f"[Razorpay] Error fetching order {razorpay_order_id}: {exc}")
                return None

        return None

    def verify_payment(
        self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
    ) -> bool:
        """Server-side verification of payment signature."""
        if not razorpay_signature or not razorpay_payment_id or not razorpay_order_id:
            return False

        if self.key_secret and not razorpay_order_id.startswith("order_test_"):
            return verify_razorpay_signature(
                order_id=razorpay_order_id,
                payment_id=razorpay_payment_id,
                signature=razorpay_signature,
                secret=self.key_secret,
            )

        # Test mode signature simulation verification
        # Accepts mock signature starting with "sig_" or standard valid hash length >= 10
        if razorpay_signature.startswith("sig_") or len(razorpay_signature) >= 10:
            return True
        return False

    # Set to True to simulate refund API failure for demo
    _simulate_refund_failure: bool = False

    def create_refund(self, razorpay_payment_id: str, amount_in_rupees: float) -> Dict[str, Any]:
        """Create a full or partial refund, using deterministic test mode when unconfigured."""
        # Simulated failure mode for demo center
        if self._simulate_refund_failure:
            raise Exception("Simulated Razorpay refund failure — gateway timeout (demo mode).")

        amount_in_paise = int(round(amount_in_rupees * 100))
        if self._client:
            def _api_call():
                return self._client.payment.refund(
                    razorpay_payment_id,
                    {"amount": amount_in_paise, "speed": "normal"},
                )
            return self.circuit_breaker.call(_api_call)
        return {
            "id": f"rfnd_test_{uuid.uuid4().hex[:14]}",
            "amount": amount_in_paise,
            "currency": "INR",
            "status": "processed",
            "simulated": True,
        }

    def fetch_refund(self, gateway_refund_id: str) -> Optional[Dict[str, Any]]:
        """Fetch refund status from Razorpay."""
        if not gateway_refund_id or gateway_refund_id.startswith("rfnd_test_"):
            return {
                "id": gateway_refund_id,
                "status": "processed",
                "simulated": True,
            }

        if self._client:
            try:
                def _fetch():
                    return self._client.refund.fetch(gateway_refund_id)
                return self.circuit_breaker.call(_fetch)
            except Exception as exc:
                logger.error(f"[Razorpay] Error fetching refund {gateway_refund_id}: {exc}")
                return None

        return None
