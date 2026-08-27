"""User and Order Repositories."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.models.user import User, BuyerProfile
from app.models.order import Order
from app.models.payment import Payment
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_buyer_profile(self, user_id: str) -> Optional[BuyerProfile]:
        result = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: AsyncSession):
        super().__init__(Order, db)

    async def get_order_with_details(self, order_id: str) -> Optional[Order]:
        result = await self.db.execute(
            select(Order)
            .options(
                joinedload(Order.buyer),
                selectinload(Order.payments),
                joinedload(Order.quote)
            )
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_orders_by_session(self, session_id: str) -> List[Order]:
        result = await self.db.execute(
            select(Order).where(Order.session_id == session_id)
        )
        return list(result.scalars().all())


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, db: AsyncSession):
        super().__init__(Payment, db)

    async def get_by_order_id(self, order_id: str) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
        )
        return result.scalar_one_or_none()
