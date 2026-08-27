"""Merchant routes — catalog and quote endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.merchant import Merchant, MerchantPolicy
from app.models.product import Product
from app.models.audit import AuditLog

router = APIRouter()


@router.get("")
async def list_merchants(db: AsyncSession = Depends(get_db)):
    """List all active merchants."""
    result = await db.execute(
        select(Merchant).where(Merchant.status == "active")
    )
    merchants = result.scalars().all()
    return {
        "merchants": [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "category": m.category,
                "trust_score": m.trust_score,
                "status": m.status,
                "policy": {
                    "max_discount_percent": m.policy.max_discount_percent,
                    "negotiation_enabled": m.policy.negotiation_enabled,
                    "min_order_value": m.policy.min_order_value,
                } if m.policy else None,
                "product_count": len(m.products) if m.products else 0,
            }
            for m in merchants
        ],
        "count": len(merchants),
    }


@router.get("/{merchant_id}")
async def get_merchant(merchant_id: str, db: AsyncSession = Depends(get_db)):
    """Get merchant details."""
    result = await db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        return {"error": "Merchant not found"}, 404
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "category": m.category,
        "trust_score": m.trust_score,
        "status": m.status,
        "policy": {
            "max_discount_percent": m.policy.max_discount_percent,
            "negotiation_enabled": m.policy.negotiation_enabled,
            "min_order_value": m.policy.min_order_value,
            "requires_merchant_approval_above": m.policy.requires_merchant_approval_above,
            "auto_discount_percent": m.policy.auto_discount_percent,
        } if m.policy else None,
    }


@router.get("/{merchant_id}/products")
async def list_merchant_products(
    merchant_id: str,
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    in_stock: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Get merchant's product catalog with optional filtering."""
    query = select(Product).where(
        Product.merchant_id == merchant_id,
        Product.active == True,
    )
    if in_stock:
        query = query.where(Product.stock > 0)
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)

    result = await db.execute(query)
    products = result.scalars().all()
    return {
        "products": [
            {
                "id": p.id,
                "merchant_id": p.merchant_id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "price": p.price,
                "currency": p.currency,
                "stock": p.stock,
                "rating": p.rating,
                "delivery_days": p.delivery_days,
                "specifications": p.specifications,
                "active": p.active,
                "refund_policy": get_refund_policy(p.category),
            }
            for p in products
        ],
        "count": len(products),
    }


from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException, status
from app.models.product import Quote
from app.services.negotiation_engine import NegotiationEngine
from app.services.refund_policy import get_refund_policy


class QuoteRequestBody(BaseModel):
    product_id: str
    session_id: Optional[str] = "demo-session-001"
    requested_discount_percent: Optional[float] = 0.0


class NegotiateRequestBody(BaseModel):
    product_id: str
    session_id: Optional[str] = "demo-session-001"
    requested_discount_percent: Optional[float] = 10.0


@router.post("/{merchant_id}/quote")
async def request_quote(
    merchant_id: str,
    body: QuoteRequestBody,
    db: AsyncSession = Depends(get_db),
):
    """Request a quote from a merchant agent with default policy discount."""
    merchant = (
        await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    ).scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")

    product = (
        await db.execute(select(Product).where(Product.id == body.product_id, Product.merchant_id == merchant_id))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this merchant.")

    policy = merchant.policy
    auto_disc = policy.auto_discount_percent if policy else 0.0
    discount_amount = round(product.price * auto_disc / 100, 2)
    final_price = round(product.price - discount_amount, 2)

    quote = Quote(
        merchant_id=merchant_id,
        product_id=product.id,
        session_id=body.session_id,
        original_price=product.price,
        discount_percent=auto_disc,
        discount_amount=discount_amount,
        final_price=final_price,
        status="active",
    )
    db.add(quote)
    db.add(AuditLog(
        session_id=body.session_id,
        actor="merchant_agent",
        action="quote_generated",
        reason=f"Quote generated for {product.name} at ₹{final_price:,.2f}.",
        amount=final_price,
        metadata_json={"quote_id": quote.id, "original_price": product.price, "discount_percent": auto_disc},
    ))
    await db.commit()
    await db.refresh(quote)

    return {
        "quote_id": quote.id,
        "merchant_id": merchant.id,
        "merchant_name": merchant.name,
        "product_id": product.id,
        "product_name": product.name,
        "original_price": quote.original_price,
        "discount_percent": quote.discount_percent,
        "discount_amount": quote.discount_amount,
        "final_price": quote.final_price,
        "status": quote.status,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
    }


@router.post("/{merchant_id}/negotiate")
async def negotiate_with_merchant(
    merchant_id: str,
    body: NegotiateRequestBody,
    db: AsyncSession = Depends(get_db),
):
    """Autonomous multi-round AI negotiation with a merchant agent."""
    merchant = (
        await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    ).scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")

    product = (
        await db.execute(select(Product).where(Product.id == body.product_id, Product.merchant_id == merchant_id))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this merchant.")

    engine = NegotiationEngine()
    policy_dict = {
        "max_discount_percent": merchant.policy.max_discount_percent if merchant.policy else 0,
        "auto_discount_percent": merchant.policy.auto_discount_percent if merchant.policy else 0,
        "negotiation_enabled": merchant.policy.negotiation_enabled if merchant.policy else False,
        "min_order_value": merchant.policy.min_order_value if merchant.policy else 0,
    }

    result = engine.negotiate(
        original_price=product.price,
        requested_discount_percent=body.requested_discount_percent,
        merchant_policy=policy_dict,
        merchant_name=merchant.name,
        session_id=body.session_id,
    )

    quote = Quote(
        merchant_id=merchant_id,
        product_id=product.id,
        session_id=body.session_id,
        original_price=result.original_price,
        discount_percent=result.approved_discount_percent,
        discount_amount=result.discount_amount,
        final_price=result.final_price,
        status="active",
    )
    db.add(quote)
    blocked = bool(result.policy_validation.get("blocked"))
    db.add(AuditLog(
        session_id=body.session_id,
        actor="merchant_agent",
        action="negotiation_blocked" if blocked else "negotiation_completed",
        reason=result.merchant_message,
        amount=result.final_price,
        policy_result={
            **result.policy_validation,
            "arithmetic_breakdown": [
                f"Requested discount: {result.requested_discount_percent}%",
                f"Maximum allowed discount: {policy_dict['max_discount_percent']}%",
                f"Difference: {result.requested_discount_percent - policy_dict['max_discount_percent']} percentage points",
            ],
            "explainability_score": 1.0,
        },
        metadata_json={"quote_id": quote.id, "negotiation_steps": result.negotiation_steps},
    ))
    await db.commit()
    await db.refresh(quote)

    return {
        "quote_id": quote.id,
        "merchant_id": merchant.id,
        "merchant_name": merchant.name,
        "product_id": product.id,
        "product_name": product.name,
        "original_price": quote.original_price,
        "requested_discount_percent": body.requested_discount_percent,
        "approved_discount_percent": quote.discount_percent,
        "discount_amount": quote.discount_amount,
        "final_price": quote.final_price,
        "merchant_message": result.merchant_message,
        "negotiation_steps": result.negotiation_steps,
        "status": quote.status,
    }

