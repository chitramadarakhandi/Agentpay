"""Base Repository class."""

from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: str) -> Optional[ModelType]:
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        result = await self.db.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def update(self, id: str, **kwargs) -> Optional[ModelType]:
        await self.db.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        await self.db.flush()
        return await self.get_by_id(id)

    async def delete(self, id: str) -> bool:
        result = await self.db.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.db.flush()
        return result.rowcount > 0
