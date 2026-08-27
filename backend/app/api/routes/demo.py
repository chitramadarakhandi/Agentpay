"""Demo routes — predefined demo scenarios."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


@router.get("/scenarios")
async def list_scenarios():
    """List available demo scenarios."""
    return {
        "scenarios": [
            {
                "id": "successful_purchase",
                "name": "Successful Transaction",
                "description": "Valid purchase → Razorpay test payment → success",
                "request": "Find me a laptop for AI/ML development under ₹80,000 with at least 16GB RAM, 512GB SSD, and delivery within 3 days.",
            },
            {
                "id": "policy_violation",
                "name": "Policy Violation",
                "description": "Attempt transaction above spending limit → blocked",
                "request": "I need a high-end workstation under ₹2,00,000 with 64GB RAM for deep learning.",
            },
            {
                "id": "negotiation",
                "name": "Negotiation",
                "description": "Buyer requests discount → merchant responds → policy validates → approved",
                "request": "Find me a gaming laptop under ₹90,000. Try to get the best discount possible.",
            },
            {
                "id": "payment_failure",
                "name": "Payment Failure",
                "description": "Payment fails → duplicate prevention → safe retry",
                "request": "Find me a budget laptop under ₹45,000 with 8GB RAM.",
            },
            {
                "id": "merchant_unavailable",
                "name": "Merchant Unavailable",
                "description": "One merchant offline → buyer continues with remaining merchants",
                "request": "Find me an ultrabook under ₹70,000 with good battery life.",
            },
            {
                "id": "refund_success",
                "name": "✅ Refund — Successful",
                "description": "Eligible order → Policy approves → Merchant approves → Razorpay refund → Real-time updates",
                "request": "I want a refund because my laptop arrived damaged.",
                "type": "refund",
            },
            {
                "id": "refund_expired",
                "name": "⏰ Refund — Window Expired",
                "description": "Old order → Refund window expired → Policy blocks → Razorpay never called",
                "request": "I want to return my laptop. I bought it two weeks ago.",
                "type": "refund",
            },
            {
                "id": "refund_failure",
                "name": "💥 Refund — Gateway Failure",
                "description": "Eligible → Approved → Razorpay fails → FAILED state → Safe retry available",
                "request": "I want a refund for a defective product.",
                "type": "refund",
            },
        ]
    }


from sqlalchemy import select
from app.models.merchant import Merchant
from app.models.product import Product, Quote
from app.services.order_service import OrderService


@router.post("/trigger-approval-demo")
async def trigger_approval_demo(db: AsyncSession = Depends(get_db)):
    """Creates a high-value order (>₹50,000) that automatically triggers the PENDING_APPROVAL gate."""
    # Find TechNova Pro 16 (or first laptop >= 50,000)
    prod_res = await db.execute(
        select(Product).where(Product.price >= 60000).limit(1)
    )
    product = prod_res.scalar_one_or_none()
    if not product:
        # Fallback to any active product
        prod_res = await db.execute(select(Product).limit(1))
        product = prod_res.scalar_one()

    # Create Quote for ₹67,500
    original_price = product.price if product.price >= 60000 else 75000.0
    discount_pct = 10.0
    discount_amount = round(original_price * 0.10, 2)
    final_price = round(original_price - discount_amount, 2)

    quote = Quote(
        merchant_id=product.merchant_id,
        product_id=product.id,
        session_id="demo-approval-session",
        original_price=original_price,
        discount_percent=discount_pct,
        discount_amount=discount_amount,
        final_price=final_price,
        status="active",
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)

    # Convert quote to order (triggers pending_approval state)
    order_svc = OrderService(db)
    order = await order_svc.create_order_from_quote(
        quote_id=quote.id,
        user_id="demo-user-001",
        session_id=quote.session_id,
    )
    await db.commit()
    enriched = await order_svc.enrich_order(order)

    return {
        "status": "pending_approval_created",
        "message": f"High-value order for ₹{order.amount:,.2f} created. Exceeds auto-approval limit of ₹50,000.",
        "order": enriched,
    }


@router.post("/launch")
async def launch_demo(db: AsyncSession = Depends(get_db)):
    """Launch a demo scenario with preloaded data."""
    return {"status": "endpoint_ready", "message": "Demo launch ready"}
