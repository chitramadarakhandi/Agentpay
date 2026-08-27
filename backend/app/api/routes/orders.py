"""Order routes — complete with concurrency locks and idempotency."""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order_service import OrderService
from app.services.idempotency_service import IdempotencyService

router = APIRouter()


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new order from an active quote.
    
    Guarantees concurrency safety (prevents duplicate orders from the same quote)
    and supports distributed idempotency with 24h TTL.
    """
    idemp_svc = IdempotencyService(db)
    
    # Check idempotency
    if idempotency_key:
        cached = await idemp_svc.check_and_start(
            idempotency_key=idempotency_key,
            endpoint="/api/orders",
            payload=body.model_dump(),
        )
        if cached:
            status_code, cached_response = cached
            return cached_response

    order_svc = OrderService(db)
    try:
        order = await order_svc.create_order_from_quote(
            quote_id=body.quote_id,
            user_id=body.user_id,
            session_id=body.session_id,
        )
        enriched = await order_svc.enrich_order(order)
        
        if idempotency_key:
            # Cache completed response
            await idemp_svc.complete(
                idempotency_key=idempotency_key,
                response_code=status.HTTP_201_CREATED,
                response_body=enriched,
            )
            
        return enriched
    except Exception as exc:
        if idempotency_key:
            await idemp_svc.fail(idempotency_key)
        raise exc


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get order details."""
    order_svc = OrderService(db)
    order = await order_svc.get_order_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )
    return await order_svc.enrich_order(order)


@router.get("")
async def list_orders(
    user_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List orders."""
    order_svc = OrderService(db)
    orders = await order_svc.list_orders(user_id=user_id, limit=limit)
    enriched_orders = [await order_svc.enrich_order(o) for o in orders]
    return {
        "orders": enriched_orders,
        "count": len(enriched_orders),
    }
