"""Merchant, MerchantPolicy, and BuyerRequest models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    policy: Mapped["MerchantPolicy"] = relationship(
        back_populates="merchant", uselist=False, lazy="joined"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="merchant", lazy="selectin"
    )
    quotes: Mapped[list["Quote"]] = relationship(
        back_populates="merchant", lazy="selectin"
    )


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=False, unique=True, index=True
    )
    max_discount_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0
    )
    min_order_value: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    allowed_categories: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=lambda: {"categories": ["electronics"]}
    )
    negotiation_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    requires_merchant_approval_above: Mapped[float] = mapped_column(
        Float, nullable=False, default=100000.0
    )
    auto_discount_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="policy")


class BuyerRequest(Base):
    __tablename__ = "buyer_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    raw_request: Mapped[str] = mapped_column(Text, nullable=False)
    structured_requirements: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="buyer_requests")


# Avoid circular imports
from app.models.product import Product, Quote  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
