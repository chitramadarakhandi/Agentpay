"""Trust & Policy Engine — deterministic transaction validation with arithmetic explainability.

CRITICAL: This engine is the safety layer between AI proposals and real money.
All financial decisions MUST pass through this engine.
LLMs may propose actions. This engine decides if they're legal and safe.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class PolicyCheck:
    """Individual policy check result with exact arithmetic formulas."""
    check_name: str
    passed: bool
    reason: str
    formula: Optional[str] = None
    arithmetic: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyResult:
    """Complete policy evaluation result with explainability breakdown."""
    allowed: bool
    requires_user_approval: bool
    reasons: List[str]
    checks: List[PolicyCheck]
    explainability_score: float = 1.0  # 1.0 = fully deterministic & explained
    arithmetic_breakdown: List[str] = field(default_factory=list)
    buyer_passport: Optional[dict] = None
    merchant_policy: Optional[dict] = None


class TrustEngine:
    """Deterministic trust and policy validation engine with explainable arithmetic.
    
    Evaluates transactions against:
    1. Buyer spending limits (single + daily) with exact deficit math
    2. Buyer category restrictions
    3. Merchant discount policies
    4. Approval thresholds
    5. Duplicate order detection
    6. Product availability
    """

    def evaluate_transaction(
        self,
        amount: float,
        discount_percent: float,
        buyer_profile: dict,
        merchant_policy: dict,
        product: dict,
        session_id: str,
        existing_orders: list[dict] = None,
    ) -> PolicyResult:
        """Evaluate a proposed transaction against all policies with mathematical proof."""
        checks = []
        reasons = []
        arithmetic_breakdown = []
        all_passed = True
        requires_approval = False

        # 1. Check buyer spending limit (single transaction)
        check = self._check_single_transaction_limit(amount, buyer_profile)
        checks.append(check)
        if check.formula:
            arithmetic_breakdown.append(check.formula)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 2. Check daily spending limit
        check = self._check_daily_limit(amount, buyer_profile)
        checks.append(check)
        if check.formula:
            arithmetic_breakdown.append(check.formula)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 3. Check category restriction
        check = self._check_category(product, buyer_profile)
        checks.append(check)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 4. Check discount against merchant policy
        check = self._check_discount_policy(discount_percent, merchant_policy)
        checks.append(check)
        if check.formula:
            arithmetic_breakdown.append(check.formula)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 5. Check product availability
        check = self._check_product_availability(product)
        checks.append(check)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 6. Check merchant minimum order
        check = self._check_min_order_value(amount, merchant_policy)
        checks.append(check)
        if check.formula:
            arithmetic_breakdown.append(check.formula)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 7. Check for duplicate orders
        check = self._check_duplicate_order(product, session_id, existing_orders or [])
        checks.append(check)
        if not check.passed:
            all_passed = False
            reasons.append(check.reason)

        # 8. Check approval requirement
        if all_passed:
            check = self._check_approval_requirement(amount, buyer_profile, merchant_policy)
            checks.append(check)
            if check.details.get("requires_approval"):
                requires_approval = True
                reasons.append(check.reason)
            else:
                reasons.append("Transaction within auto-approval threshold")

        # Positive summary reasons
        if all_passed:
            positive_reasons = [
                f"Amount ₹{amount:,.0f} is within single transaction limit ₹{buyer_profile.get('single_transaction_limit', 0):,.0f}",
                f"Amount is within daily spending limit",
                f"Discount {discount_percent}% is within merchant policy ({merchant_policy.get('max_discount_percent', 0)}% max)",
                f"Product is in stock ({product.get('stock', 0)} units)",
            ]
            reasons = positive_reasons + reasons

        return PolicyResult(
            allowed=all_passed,
            requires_user_approval=requires_approval,
            reasons=reasons,
            checks=checks,
            explainability_score=1.0,
            arithmetic_breakdown=arithmetic_breakdown,
            buyer_passport={
                "single_transaction_limit": buyer_profile.get("single_transaction_limit"),
                "daily_spending_limit": buyer_profile.get("daily_spending_limit"),
                "daily_spent": buyer_profile.get("daily_spent", 0),
                "requires_approval_above": buyer_profile.get("requires_approval_above"),
                "allowed_categories": buyer_profile.get("allowed_categories", {}).get("categories", []),
                "status": buyer_profile.get("status"),
            },
            merchant_policy={
                "max_discount_percent": merchant_policy.get("max_discount_percent"),
                "negotiation_enabled": merchant_policy.get("negotiation_enabled"),
                "min_order_value": merchant_policy.get("min_order_value"),
            },
        )

    def _check_single_transaction_limit(self, amount: float, profile: dict) -> PolicyCheck:
        limit = profile.get("single_transaction_limit", 0.0)
        passed = amount <= limit
        deficit = round(amount - limit, 2) if not passed else 0.0
        formula = f"₹{amount:,.2f} requested {'<=' if passed else '>'} ₹{limit:,.2f} limit (Deficit: ₹{deficit:,.2f})" if not passed else f"₹{amount:,.2f} requested <= ₹{limit:,.2f} limit (Margin: ₹{limit - amount:,.2f})"
        
        return PolicyCheck(
            check_name="single_transaction_limit",
            passed=passed,
            reason=f"Transaction ₹{amount:,.2f} {'is within' if passed else 'exceeds'} single transaction limit ₹{limit:,.2f} [Deficit: ₹{deficit:,.2f}]",
            formula=formula,
            arithmetic={"amount": amount, "limit": limit, "deficit": deficit, "passed": passed},
            details={"amount": amount, "limit": limit},
        )

    def _check_daily_limit(self, amount: float, profile: dict) -> PolicyCheck:
        limit = profile.get("daily_spending_limit", 0.0)
        spent = profile.get("daily_spent", 0.0)
        remaining = limit - spent
        total_projected = spent + amount
        passed = total_projected <= limit
        deficit = round(total_projected - limit, 2) if not passed else 0.0
        
        formula = f"daily_spent (₹{spent:,.2f}) + requested (₹{amount:,.2f}) = projected (₹{total_projected:,.2f}) {'<=' if passed else '>'} limit (₹{limit:,.2f}) [Deficit: ₹{deficit:,.2f}]"
        
        return PolicyCheck(
            check_name="daily_spending_limit",
            passed=passed,
            reason=f"Projected daily spend ₹{total_projected:,.2f} (spent: ₹{spent:,.2f} + req: ₹{amount:,.2f}) {'is within' if passed else 'exceeds'} daily limit ₹{limit:,.2f} [Deficit: ₹{deficit:,.2f}]",
            formula=formula,
            arithmetic={
                "daily_spent": spent,
                "requested": amount,
                "projected_total": total_projected,
                "daily_limit": limit,
                "remaining_before": remaining,
                "deficit": deficit,
                "passed": passed,
            },
            details={"amount": amount, "limit": limit, "spent": spent, "remaining": remaining},
        )

    def _check_category(self, product: dict, profile: dict) -> PolicyCheck:
        allowed = profile.get("allowed_categories", {}).get("categories", [])
        product_cat = product.get("category", "").lower()
        passed = not allowed or any(
            cat.lower() in product_cat or product_cat in cat.lower()
            for cat in allowed
        )
        return PolicyCheck(
            check_name="category_restriction",
            passed=passed,
            reason=f"Category '{product_cat}' is {'whitelisted' if passed else 'FORBIDDEN (Whitelisted: ' + str(allowed) + ')'}",
            formula=f"category '{product_cat}' in {allowed} => {passed}",
            arithmetic={"product_category": product_cat, "allowed_whitelist": allowed, "passed": passed},
            details={"product_category": product_cat, "allowed": allowed},
        )

    def _check_discount_policy(self, discount_pct: float, policy: dict) -> PolicyCheck:
        max_discount = policy.get("max_discount_percent", 0.0)
        passed = discount_pct <= max_discount
        excess = round(discount_pct - max_discount, 2) if not passed else 0.0
        formula = f"discount ({discount_pct}%) {'<=' if passed else '>'} merchant_max ({max_discount}%) [Excess: {excess}%]"
        
        return PolicyCheck(
            check_name="discount_policy",
            passed=passed,
            reason=f"Requested discount {discount_pct}% {'is within' if passed else 'exceeds'} merchant maximum {max_discount}% [Excess: {excess}%]",
            formula=formula,
            arithmetic={"requested_discount": discount_pct, "max_allowed": max_discount, "excess": excess, "passed": passed},
            details={"requested": discount_pct, "max_allowed": max_discount},
        )

    def _check_product_availability(self, product: dict) -> PolicyCheck:
        stock = product.get("stock", 0)
        active = product.get("active", True)
        passed = stock > 0 and active
        reason = "Product is available" if passed else (
            f"Product is out of stock ({stock} available)" if stock <= 0 else "Product is inactive"
        )
        return PolicyCheck(
            check_name="product_availability",
            passed=passed,
            reason=reason,
            formula=f"stock ({stock}) > 0 and active ({active}) => {passed}",
            arithmetic={"stock": stock, "active": active, "passed": passed},
            details={"stock": stock, "active": active},
        )

    def _check_min_order_value(self, amount: float, policy: dict) -> PolicyCheck:
        min_val = policy.get("min_order_value", 0.0)
        passed = amount >= min_val
        deficit = round(min_val - amount, 2) if not passed else 0.0
        formula = f"order_amount (₹{amount:,.2f}) {'>=' if passed else '<'} min_order_value (₹{min_val:,.2f}) [Deficit: ₹{deficit:,.2f}]"
        
        return PolicyCheck(
            check_name="minimum_order_value",
            passed=passed,
            reason=f"Amount ₹{amount:,.2f} {'meets' if passed else 'is below'} minimum order value ₹{min_val:,.2f} [Deficit: ₹{deficit:,.2f}]",
            formula=formula,
            arithmetic={"amount": amount, "min_order_value": min_val, "deficit": deficit, "passed": passed},
            details={"amount": amount, "minimum": min_val},
        )

    def _check_duplicate_order(
        self, product: dict, session_id: str, existing_orders: list[dict]
    ) -> PolicyCheck:
        product_id = product.get("id", "")
        duplicates = [
            o for o in existing_orders
            if o.get("product_id") == product_id
            and o.get("session_id") == session_id
            and o.get("status") in ("created", "pending", "success")
        ]
        passed = len(duplicates) == 0
        return PolicyCheck(
            check_name="duplicate_order",
            passed=passed,
            reason="No duplicate order detected" if passed else f"Duplicate order detected: {len(duplicates)} existing order(s) for this product",
            formula=f"existing_active_orders_for_item ({len(duplicates)}) == 0 => {passed}",
            arithmetic={"duplicate_count": len(duplicates), "passed": passed},
            details={"duplicate_count": len(duplicates)},
        )

    def _check_approval_requirement(
        self, amount: float, profile: dict, policy: dict
    ) -> PolicyCheck:
        buyer_threshold = profile.get("requires_approval_above", 0.0)
        merchant_threshold = policy.get("requires_merchant_approval_above", float("inf"))
        
        needs_buyer_approval = amount > buyer_threshold
        needs_merchant_approval = amount > merchant_threshold
        requires = needs_buyer_approval or needs_merchant_approval
        
        reason_parts = []
        if needs_buyer_approval:
            reason_parts.append(f"Amount ₹{amount:,.2f} exceeds buyer approval threshold ₹{buyer_threshold:,.2f}")
        if needs_merchant_approval:
            reason_parts.append(f"Amount ₹{amount:,.2f} exceeds merchant approval threshold ₹{merchant_threshold:,.2f}")
        if not requires:
            reason_parts.append("Amount within autonomous auto-approval limits")
        
        formula = f"amount (₹{amount:,.2f}) > buyer_threshold (₹{buyer_threshold:,.2f}) => requires_approval={requires}"
        
        return PolicyCheck(
            check_name="approval_requirement",
            passed=True,
            reason="; ".join(reason_parts),
            formula=formula,
            arithmetic={
                "amount": amount,
                "buyer_threshold": buyer_threshold,
                "merchant_threshold": merchant_threshold if merchant_threshold != float("inf") else "inf",
                "requires_approval": requires,
            },
            details={
                "requires_approval": requires,
                "buyer_threshold": buyer_threshold,
                "merchant_threshold": merchant_threshold,
            },
        )
