"""Subscription and Mandate models for Agent AutoPay.

Enables AI agents to operate on recurring monthly allowances
governed by e-Mandate rules (Razorpay Subscriptions simulation).
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def next_month():
    return datetime.now(timezone.utc) + timedelta(days=30)


# Valid subscription state transitions
SUBSCRIPTION_STATE_TRANSITIONS = {
    "active": ["paused", "cancelled", "completed"],
    "paused": ["active", "cancelled"],
    "cancelled": [],  # Terminal
    "completed": [],  # Terminal
}


class Subscription(Base):
    """Agent AutoPay subscription with recurring mandate."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    amount_per_cycle: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )  # monthly, weekly
    max_cycles: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    current_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, paused, cancelled, completed
    mandate_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True
    )  # Razorpay mandate reference
    razorpay_subscription_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True
    )
    next_charge_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=next_month
    )
    total_charged: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    charges: Mapped[list["SubscriptionCharge"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a state transition is valid."""
        allowed = SUBSCRIPTION_STATE_TRANSITIONS.get(self.status, [])
        return new_status in allowed


class SubscriptionCharge(Base):
    """Individual recurring charge within a subscription cycle."""

    __tablename__ = "subscription_charges"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, success, failed
    razorpay_payment_id: Mapped[str] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="charges")
