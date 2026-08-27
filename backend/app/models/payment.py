"""Payment model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id"), nullable=False, index=True
    )
    razorpay_payment_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    razorpay_signature: Mapped[str] = mapped_column(String(500), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created"
    )  # created, pending, success, failed, cancelled
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="payments")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment", lazy="selectin")


from app.models.order import Order  # noqa: E402, F401
from app.models.refund import Refund  # noqa: E402, F401
