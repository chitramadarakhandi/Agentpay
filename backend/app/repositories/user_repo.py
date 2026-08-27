"""Missing UserRepository import fix."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, BuyerProfile
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_buyer_profile(self, user_id: str):
        result = await self.db.execute(
            select(BuyerProfile).where(BuyerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
