"""User and BuyerProfile models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    buyer_profile: Mapped["BuyerProfile"] = relationship(
        back_populates="user", uselist=False, lazy="joined"
    )
    buyer_requests: Mapped[list["BuyerRequest"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="buyer", lazy="selectin"
    )


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    daily_spending_limit: Mapped[float] = mapped_column(
        Float, nullable=False, default=150000.0
    )
    single_transaction_limit: Mapped[float] = mapped_column(
        Float, nullable=False, default=80000.0
    )
    requires_approval_above: Mapped[float] = mapped_column(
        Float, nullable=False, default=50000.0
    )
    allowed_categories: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=lambda: {"categories": ["electronics", "laptops", "phones", "accessories"]}
    )
    daily_spent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="buyer_profile")


# Import these at the bottom to avoid circular imports
from app.models.order import Order  # noqa: E402, F401
from app.models.merchant import BuyerRequest  # noqa: E402, F401
