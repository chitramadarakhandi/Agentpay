"""Deterministic refund policy engine with structured per-check verdicts.

Every eligibility decision is broken down into individually-verifiable checks.
The LLM never invents policy reasons — all explanations come from this engine.
"""

from datetime import datetime, timedelta, timezone
from typing import Any


# ── Category-specific refund policies ─────────────────────────
POLICIES = {
    "laptops":     {"window_days": 10, "refund_percent": 100, "condition": "Unused or defective; original accessories required."},
    "phones":      {"window_days": 7,  "refund_percent": 100, "condition": "Unused or defective; original packaging required."},
    "accessories": {"window_days": 7,  "refund_percent": 100, "condition": "Unused and in resalable condition."},
}
DEFAULT_POLICY = {"window_days": 7, "refund_percent": 100, "condition": "Unused, undamaged, and returned with original packaging."}

# High-value refund threshold — above this, merchant approval is always required
HIGH_VALUE_REFUND_THRESHOLD = 50000.0


def get_refund_policy(category: str | None) -> dict:
    """Get the refund policy for a given product category."""
    policy = dict(POLICIES.get((category or "").lower(), DEFAULT_POLICY))
    policy["category"] = category or "general"
    return policy


def refund_deadline(created_at: datetime, window_days: int) -> datetime:
    """Calculate the refund deadline from the order creation date."""
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return created + timedelta(days=window_days)


class EligibilityCheck:
    """Represents a single eligibility check result."""
    def __init__(self, check_id: str, label: str, passed: bool, detail: str):
        self.check_id = check_id
        self.label = label
        self.passed = passed
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "label": self.label,
            "passed": self.passed,
            "detail": self.detail,
        }


class EligibilityResult:
    """Structured result of a full refund eligibility evaluation."""
    def __init__(self):
        self.checks: list[EligibilityCheck] = []
        self.eligible = True
        self.blocking_reason = ""

    def add_check(self, check: EligibilityCheck):
        self.checks.append(check)
        if not check.passed and self.eligible:
            self.eligible = False
            self.blocking_reason = check.detail

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "decision": "accepted" if self.eligible else "rejected",
            "decision_reason": "Refund is available under the product policy." if self.eligible else self.blocking_reason,
            "checks": [c.to_dict() for c in self.checks],
        }


def evaluate_refund_eligibility(
    order: Any,
    payment: Any,
    product: Any,
    refunded_total: float,
    requested_amount: float | None,
    active_refund_exists: bool,
    buyer_id: str | None = None,
) -> EligibilityResult:
    """Run all deterministic eligibility checks. Returns structured result.

    This is the single source of truth for refund eligibility.
    The LLM must never override these checks.
    """
    result = EligibilityResult()

    # Check 1: Order exists
    if order is None:
        result.add_check(EligibilityCheck(
            "order_exists", "Order exists", False, "Order ID was not found."
        ))
        return result
    result.add_check(EligibilityCheck(
        "order_exists", "Order exists", True, f"Order {order.id} found."
    ))

    # Check 2: Payment was successful
    if payment is None or payment.status != "success":
        result.add_check(EligibilityCheck(
            "payment_successful", "Payment verified", False,
            "A successful payment is required before requesting a refund."
        ))
        return result
    result.add_check(EligibilityCheck(
        "payment_successful", "Payment verified", True,
        f"Payment of ₹{payment.amount:,.2f} confirmed."
    ))

    # Check 3: Order status is success
    if order.status != "success":
        result.add_check(EligibilityCheck(
            "order_status", "Order completed", False,
            f"Only successfully completed orders can be refunded. Current status: {order.status}."
        ))
        return result
    result.add_check(EligibilityCheck(
        "order_status", "Order completed", True,
        "Order was completed successfully."
    ))

    # Check 4: Order belongs to customer (if buyer_id provided)
    if buyer_id and order.buyer_id != buyer_id:
        result.add_check(EligibilityCheck(
            "ownership", "Order ownership", False,
            "This order does not belong to the requesting customer."
        ))
        return result
    result.add_check(EligibilityCheck(
        "ownership", "Order ownership", True,
        "Order belongs to the requesting customer."
    ))

    # Check 5: No active refund in progress
    if active_refund_exists:
        result.add_check(EligibilityCheck(
            "no_active_refund", "No active refund", False,
            "A refund is already in progress for this order. Please wait for it to complete."
        ))
        return result
    result.add_check(EligibilityCheck(
        "no_active_refund", "No active refund", True,
        "No refund currently in progress."
    ))

    # Check 6: Within refund window
    policy = get_refund_policy(product.category if product else None)
    deadline = refund_deadline(order.created_at, policy["window_days"])
    now = datetime.now(timezone.utc)
    within_window = now <= deadline
    if not within_window:
        days_elapsed = (now - (order.created_at if order.created_at.tzinfo else order.created_at.replace(tzinfo=timezone.utc))).days
        result.add_check(EligibilityCheck(
            "refund_window", "Within refund window", False,
            f"Refund window expired. Window: {policy['window_days']} days. Order age: {days_elapsed} days."
        ))
    else:
        result.add_check(EligibilityCheck(
            "refund_window", "Within refund window", True,
            f"Order is within the {policy['window_days']}-day refund window. Deadline: {deadline.strftime('%Y-%m-%d')}."
        ))

    # Check 7: Refundable amount remaining
    remaining = round(payment.amount - refunded_total, 2)
    if remaining <= 0:
        result.add_check(EligibilityCheck(
            "refundable_amount", "Refundable amount available", False,
            "This order has no remaining refundable balance. Full refund has already been processed."
        ))
    else:
        result.add_check(EligibilityCheck(
            "refundable_amount", "Refundable amount available", True,
            f"Remaining refundable: ₹{remaining:,.2f} of ₹{payment.amount:,.2f} paid."
        ))

    # Check 8: Requested amount valid (if specified)
    if requested_amount is not None:
        if requested_amount <= 0 or requested_amount > remaining:
            result.add_check(EligibilityCheck(
                "amount_valid", "Requested amount valid", False,
                f"Requested ₹{requested_amount:,.2f} but only ₹{remaining:,.2f} is refundable."
            ))
        else:
            result.add_check(EligibilityCheck(
                "amount_valid", "Requested amount valid", True,
                f"Requested ₹{requested_amount:,.2f} is within the refundable balance of ₹{remaining:,.2f}."
            ))

    # Check 9: Category policy
    result.add_check(EligibilityCheck(
        "category_policy", "Category policy met", within_window and remaining > 0,
        f"{policy['category'].title()}: {policy['condition']}"
    ))

    return result


def requires_merchant_approval(amount: float) -> bool:
    """Determine if a refund amount requires explicit merchant approval."""
    return amount >= HIGH_VALUE_REFUND_THRESHOLD
