"""Order model with state machine."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# Valid order state transitions
ORDER_STATE_TRANSITIONS = {
    "pending_approval": ["created", "cancelled"],  # Human-in-the-loop gate
    "created": ["pending", "cancelled"],
    "pending": ["success", "failed", "cancelled"],
    "success": [],  # Terminal state
    "failed": ["pending"],  # Allow retry
    "cancelled": [],  # Terminal state
}


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    buyer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=True, unique=True, index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created"
    )  # created, pending, success, failed, cancelled
    razorpay_order_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    buyer: Mapped["User"] = relationship(back_populates="orders")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", lazy="selectin"
    )
    refunds: Mapped[list["Refund"]] = relationship(
        back_populates="order", lazy="selectin"
    )
    quote: Mapped["Quote"] = relationship(back_populates="order")

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a state transition is valid."""
        allowed = ORDER_STATE_TRANSITIONS.get(self.status, [])
        return new_status in allowed


from app.models.user import User  # noqa: E402, F401
from app.models.payment import Payment  # noqa: E402, F401
from app.models.product import Quote  # noqa: E402, F401
from app.models.refund import Refund  # noqa: E402, F401
