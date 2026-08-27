"""Merchant and Product Repositories."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.models.merchant import Merchant, MerchantPolicy
from app.models.product import Product, Quote
from app.repositories.base import BaseRepository


class MerchantRepository(BaseRepository[Merchant]):
    def __init__(self, db: AsyncSession):
        super().__init__(Merchant, db)

    async def get_active_merchants(self) -> List[Merchant]:
        result = await self.db.execute(
            select(Merchant)
            .options(joinedload(Merchant.policy), selectinload(Merchant.products))
            .where(Merchant.status == "active")
        )
        return list(result.scalars().unique().all())

    async def get_merchant_with_policy(self, merchant_id: str) -> Optional[Merchant]:
        result = await self.db.execute(
            select(Merchant)
            .options(joinedload(Merchant.policy))
            .where(Merchant.id == merchant_id)
        )
        return result.scalar_one_or_none()


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: AsyncSession):
        super().__init__(Product, db)

    async def get_active_products_by_category(self, category: Optional[str] = None) -> List[Product]:
        query = (
            select(Product)
            .options(joinedload(Product.merchant).joinedload(Merchant.policy))
            .where(Product.active == True)
        )
        if category:
            query = query.where(Product.category == category)
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def get_product_with_merchant(self, product_id: str) -> Optional[Product]:
        result = await self.db.execute(
            select(Product)
            .options(joinedload(Product.merchant).joinedload(Merchant.policy))
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()


class QuoteRepository(BaseRepository[Quote]):
    def __init__(self, db: AsyncSession):
        super().__init__(Quote, db)

    async def get_quote_with_details(self, quote_id: str) -> Optional[Quote]:
        result = await self.db.execute(
            select(Quote)
            .options(
                joinedload(Quote.merchant).joinedload(Merchant.policy),
                joinedload(Quote.product)
            )
            .where(Quote.id == quote_id)
        )
        return result.scalar_one_or_none()
