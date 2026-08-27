"""Product and Quote models."""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def quote_expiry():
    return datetime.now(timezone.utc) + timedelta(hours=1)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    specifications: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="products")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="product", lazy="selectin")


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    original_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_price: Mapped[float] = mapped_column(Float, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=quote_expiry
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, accepted, expired, rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="quotes")
    product: Mapped["Product"] = relationship(back_populates="quotes")
    order: Mapped["Order"] = relationship(back_populates="quote", uselist=False)


from app.models.merchant import Merchant  # noqa: E402, F401
from app.models.order import Order  # noqa: E402, F401
