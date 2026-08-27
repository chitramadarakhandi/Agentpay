"""Policy + Trust Center routes — with dry-run simulation and arithmetic explainability."""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.api.deps import get_db
from app.models.user import BuyerProfile, User
from app.models.merchant import Merchant
from app.models.product import Product
from app.policies.trust_engine import TrustEngine
from app.audit.audit_service import AuditService
from app.services.order_service import OrderService

router = APIRouter()


class PolicyEvalBody(BaseModel):
    user_id: str = "demo-user-001"
    merchant_id: str
    product_id: str
    amount: float
    discount_percent: float = 0.0
    session_id: str


class PolicySimulationBody(BaseModel):
    """Payload for dry-run simulation before commit (zero DB side-effects)."""
    user_id: Optional[str] = "demo-user-001"
    amount: float
    discount_percent: float = 0.0
    category: str = "laptops"
    product_name: str = "Simulated Item"
    stock: int = 5
    active: bool = True
    session_id: str = "sim-session-001"
    # Optional passport overrides for what-if analysis
    override_single_limit: Optional[float] = None
    override_daily_limit: Optional[float] = None
    override_daily_spent: Optional[float] = None
    override_merchant_max_discount: Optional[float] = None


@router.post("/simulate")
async def simulate_policy_dry_run(
    body: PolicySimulationBody,
    db: AsyncSession = Depends(get_db),
):
    """
    Dry-run Policy Simulator (Pre-flight authorization check).
    
    Runs the full deterministic policy gauntlet with arithmetic breakdown
    WITHOUT writing any records to the database or touching payment gateways.
    Enables what-if simulations and pre-commitment authorization holds.
    """
    # Fetch base profile if exists
    profile_r = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == body.user_id))
    profile = profile_r.scalar_one_or_none()

    single_limit = body.override_single_limit if body.override_single_limit is not None else (profile.single_transaction_limit if profile else 80000.0)
    daily_limit = body.override_daily_limit if body.override_daily_limit is not None else (profile.daily_spending_limit if profile else 150000.0)
    daily_spent = body.override_daily_spent if body.override_daily_spent is not None else (profile.daily_spent if profile else 0.0)
    approval_above = profile.requires_approval_above if profile else 50000.0
    allowed_categories = profile.allowed_categories if profile else {"categories": ["electronics", "laptops", "phones", "accessories"]}

    max_discount = body.override_merchant_max_discount if body.override_merchant_max_discount is not None else 15.0

    trust = TrustEngine()
    result = trust.evaluate_transaction(
        amount=body.amount,
        discount_percent=body.discount_percent,
        buyer_profile={
            "single_transaction_limit": single_limit,
            "daily_spending_limit": daily_limit,
            "daily_spent": daily_spent,
            "requires_approval_above": approval_above,
            "allowed_categories": allowed_categories,
            "status": "active",
        },
        merchant_policy={
            "max_discount_percent": max_discount,
            "negotiation_enabled": True,
            "min_order_value": 500.0,
            "requires_merchant_approval_above": 100000.0,
        },
        product={
            "id": "sim-prod-1",
            "name": body.product_name,
            "category": body.category,
            "stock": body.stock,
            "active": body.active,
        },
        session_id=body.session_id,
    )

    return {
        "simulation_mode": True,
        "side_effects": "none (dry-run only)",
        "allowed": result.allowed,
        "requires_user_approval": result.requires_user_approval,
        "explainability_score": result.explainability_score,
        "reasons": result.reasons,
        "arithmetic_breakdown": result.arithmetic_breakdown,
        "checks": [
            {
                "name": c.check_name,
                "passed": c.passed,
                "reason": c.reason,
                "formula": c.formula,
                "arithmetic": c.arithmetic,
            }
            for c in result.checks
        ],
        "projected_daily_remaining": max(0.0, daily_limit - (daily_spent + (body.amount if result.allowed else 0.0))),
        "buyer_passport": result.buyer_passport,
        "merchant_policy": result.merchant_policy,
    }


@router.post("/evaluate")
async def evaluate_policy(body: PolicyEvalBody, db: AsyncSession = Depends(get_db)):
    """Evaluate a transaction against buyer + merchant policies and log violations if blocked."""
    audit = AuditService(db)

    profile_r = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == body.user_id))
    profile = profile_r.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Buyer profile not found.")

    product_r = await db.execute(select(Product).where(Product.id == body.product_id))
    product = product_r.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    merchant_r = await db.execute(select(Merchant).where(Merchant.id == body.merchant_id))
    merchant = merchant_r.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")

    policy = merchant.policy
    trust = TrustEngine()
    result = trust.evaluate_transaction(
        amount=body.amount,
        discount_percent=body.discount_percent,
        buyer_profile={
            "single_transaction_limit": profile.single_transaction_limit,
            "daily_spending_limit": profile.daily_spending_limit,
            "daily_spent": profile.daily_spent,
            "requires_approval_above": profile.requires_approval_above,
            "allowed_categories": profile.allowed_categories,
            "status": profile.status,
        },
        merchant_policy={
            "max_discount_percent": policy.max_discount_percent if policy else 0,
            "negotiation_enabled": policy.negotiation_enabled if policy else False,
            "min_order_value": policy.min_order_value if policy else 0,
            "requires_merchant_approval_above": policy.requires_merchant_approval_above if policy else 999999,
        },
        product={"id": product.id, "category": product.category, "stock": product.stock, "active": product.active},
        session_id=body.session_id,
    )

    if not result.allowed:
        for check in result.checks:
            if not check.passed:
                await audit.log_policy_violation(
                    session_id=body.session_id,
                    policy_type=check.check_name,
                    requested_value=str(body.amount),
                    allowed_value=str(check.details.get("limit", "N/A")),
                    reason=check.reason,
                )
    await audit.log_action(
        session_id=body.session_id,
        actor="policy_engine",
        action="policy_blocked" if not result.allowed else "policy_evaluated",
        reason=result.reasons[0] if result.reasons else "All policy checks passed.",
        amount=body.amount,
        policy_result={
            "allowed": result.allowed,
            "requires_user_approval": result.requires_user_approval,
            "arithmetic_breakdown": result.arithmetic_breakdown,
            "explainability_score": result.explainability_score,
        },
        metadata={"checks": [c.check_name for c in result.checks]},
    )
    await db.commit()

    return {
        "allowed": result.allowed,
        "requires_user_approval": result.requires_user_approval,
        "explainability_score": result.explainability_score,
        "reasons": result.reasons,
        "arithmetic_breakdown": result.arithmetic_breakdown,
        "checks": [
            {
                "name": c.check_name,
                "passed": c.passed,
                "reason": c.reason,
                "formula": c.formula,
                "arithmetic": c.arithmetic,
            }
            for c in result.checks
        ],
        "buyer_passport": result.buyer_passport,
        "merchant_policy": result.merchant_policy,
    }


@router.get("/passport/{user_id}")
async def get_passport(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get buyer's AI Spending Passport."""
    profile_r = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == user_id))
    profile = profile_r.scalar_one_or_none()
    user_r = await db.execute(select(User).where(User.id == user_id))
    user = user_r.scalar_one_or_none()
    if not profile or not user:
        raise HTTPException(status_code=404, detail="Buyer profile not found.")

    cats = profile.allowed_categories.get("categories", []) if isinstance(profile.allowed_categories, dict) else []
    return {
        "user_id": user.id,
        "user_name": user.name,
        "single_transaction_limit": profile.single_transaction_limit,
        "daily_spending_limit": profile.daily_spending_limit,
        "daily_spent": profile.daily_spent,
        "daily_remaining": max(0.0, profile.daily_spending_limit - profile.daily_spent),
        "requires_approval_above": profile.requires_approval_above,
        "allowed_categories": cats,
        "max_ai_discount_authority": 2000.0,
        "status": profile.status,
    }


@router.get("/violations")
async def list_violations(db: AsyncSession = Depends(get_db)):
    """Recent policy violations."""
    audit = AuditService(db)
    return {"violations": await audit.get_violations(limit=50)}


@router.get("/approvals/pending")
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    """List orders currently blocked in 'pending_approval' awaiting human authorization."""
    order_svc = OrderService(db)
    orders = await order_svc.list_pending_approvals(limit=50)
    enriched = [await order_svc.enrich_order(o) for o in orders]
    return {
        "pending_approvals": enriched,
        "count": len(enriched),
    }


class ApprovalActionBody(BaseModel):
    approver: str = "human_admin"
    reason: Optional[str] = None


@router.post("/approvals/{order_id}/approve")
async def approve_pending_order(
    order_id: str,
    body: ApprovalActionBody = Body(default_factory=ApprovalActionBody),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending high-value or gated order, enabling payment processing."""
    order_svc = OrderService(db)
    order = await order_svc.approve_order(order_id=order_id, approver=body.approver)
    await db.commit()
    return {
        "status": "approved",
        "message": f"Order {order_id} has been authorized by {body.approver}. Ready for payment.",
        "order": await order_svc.enrich_order(order),
    }


@router.post("/approvals/{order_id}/reject")
async def reject_pending_order(
    order_id: str,
    body: ApprovalActionBody = Body(default_factory=ApprovalActionBody),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending order, moving it to cancelled."""
    order_svc = OrderService(db)
    order = await order_svc.reject_order(
        order_id=order_id,
        reason=body.reason or "Rejected by human administrator",
        rejecter=body.approver,
    )
    await db.commit()
    return {
        "status": "rejected",
        "message": f"Order {order_id} has been rejected.",
        "order": await order_svc.enrich_order(order),
    }

