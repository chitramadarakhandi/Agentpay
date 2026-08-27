"""Analytics routes — real metrics from DB."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.api.deps import get_db
from app.models.order import Order
from app.models.payment import Payment
from app.models.merchant import BuyerRequest, Merchant
from app.models.audit import PolicyViolation, AuditLog

router = APIRouter()


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    """Real analytics calculated from DB."""
    total_requests = (await db.execute(select(func.count()).select_from(BuyerRequest))).scalar() or 0
    total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar() or 0
    successful_orders = (await db.execute(
        select(func.count()).select_from(Order).where(Order.status == "success")
    )).scalar() or 0
    failed_orders = (await db.execute(
        select(func.count()).select_from(Order).where(Order.status == "failed")
    )).scalar() or 0
    total_violations = (await db.execute(select(func.count()).select_from(PolicyViolation))).scalar() or 0
    total_revenue_r = await db.execute(
        select(func.sum(Order.amount)).where(Order.status == "success")
    )
    total_revenue = total_revenue_r.scalar() or 0.0
    avg_order_r = await db.execute(
        select(func.avg(Order.amount)).where(Order.status == "success")
    )
    avg_order = avg_order_r.scalar() or 0.0

    conversion_rate = round((successful_orders / total_orders * 100), 1) if total_orders else 0
    payment_success_rate = round((successful_orders / (successful_orders + failed_orders) * 100), 1) if (successful_orders + failed_orders) else 0

    # Orders by status
    orders_result = await db.execute(select(Order.status, func.count()).group_by(Order.status))
    orders_by_status = dict(orders_result.all())

    # Recent orders
    recent_orders_r = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )
    recent_orders = recent_orders_r.scalars().all()

    return {
        "ai_buyer_requests": total_requests,
        "total_orders": total_orders,
        "successful_orders": successful_orders,
        "failed_orders": failed_orders,
        "total_revenue": round(total_revenue, 2),
        "average_order_value": round(avg_order, 2),
        "transaction_conversion_rate": conversion_rate,
        "payment_success_rate": payment_success_rate,
        "blocked_policy_actions": total_violations,
        "orders_by_status": orders_by_status,
        "recent_orders": [
            {"id": o.id[:8], "amount": o.amount, "status": o.status, "session_id": o.session_id[:8]}
            for o in recent_orders
        ],
    }


@router.get("/merchants")
async def get_merchant_analytics(db: AsyncSession = Depends(get_db)):
    """Per-merchant analytics."""
    merchants_r = await db.execute(select(Merchant).where(Merchant.status == "active"))
    merchants = merchants_r.scalars().all()

    result = []
    for m in merchants:
        orders_r = await db.execute(
            select(func.count(), func.sum(Order.amount)).where(
                Order.merchant_id == m.id, Order.status == "success"
            )
        )
        row = orders_r.one()
        count, revenue = row[0] or 0, row[1] or 0.0
        result.append({
            "merchant_id": m.id,
            "merchant_name": m.name,
            "trust_score": m.trust_score,
            "total_orders": count,
            "total_revenue": round(revenue, 2),
            "product_count": len(m.products) if m.products else 0,
        })
    return {"merchants": result}
