"""Split Payment and Settlement models for Razorpay Route.

Enables multi-vendor split settlement where a single payment is
automatically distributed across multiple merchants with a platform fee.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SplitPayment(Base):
    """Multi-vendor split payment container (Razorpay Route)."""

    __tablename__ = "split_payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(
        String(36), nullable=True, index=True
    )  # Optional link to existing order
    session_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    platform_fee_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0
    )
    platform_fee_amount: Mapped[float] = mapped_column(Float, nullable=False)
    net_merchant_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created"
    )  # created, processing, settled, failed
    razorpay_order_id: Mapped[str] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    settlements: Mapped[list["SplitSettlement"]] = relationship(
        back_populates="split_payment", lazy="selectin"
    )


class SplitSettlement(Base):
    """Individual merchant settlement within a split payment."""

    __tablename__ = "split_settlements"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    split_payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("split_payments.id"), nullable=False, index=True
    )
    merchant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    percent_share: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, settled, failed
    razorpay_transfer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    split_payment: Mapped["SplitPayment"] = relationship(back_populates="settlements")
