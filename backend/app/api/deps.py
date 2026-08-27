"""FastAPI dependency injection."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session


async def get_db() -> AsyncSession:
    """Yield database session for request lifecycle."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
