"""Refund model and lifecycle state machine."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ── Refund State Machine ──────────────────────────────────────
# Valid transitions between refund states.
# Terminal states (processed, rejected, failed, cancelled) allow no outbound transitions.
REFUND_STATE_TRANSITIONS = {
    "requested":          ["eligibility_check", "rejected"],
    "eligibility_check":  ["pending_approval", "rejected", "failed"],
    "pending_approval":   ["approved", "rejected", "cancelled"],
    "approved":           ["processing", "failed"],
    "processing":         ["processed", "failed"],
    "processed":          [],          # Terminal ✓
    "rejected":           [],          # Terminal ✗
    "failed":             ["processing"],  # Allow retry
    "cancelled":          [],          # Terminal ✗
}

TERMINAL_STATES = {"processed", "rejected", "failed", "cancelled"}
ACTIVE_STATES = {"requested", "eligibility_check", "pending_approval", "approved", "processing"}


def utcnow():
    return datetime.now(timezone.utc)


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id"), nullable=False, index=True
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id"), nullable=False, index=True
    )
    buyer_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    approved_amount: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    refund_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full"
    )  # full, partial
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="requested", index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    gateway_refund_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True
    )
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)
    policy_result: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    ai_recommendation: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    order: Mapped["Order"] = relationship(back_populates="refunds")
    payment: Mapped["Payment"] = relationship(back_populates="refunds")
    events: Mapped[list["RefundEvent"]] = relationship(
        back_populates="refund", lazy="selectin", order_by="RefundEvent.created_at"
    )

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a state transition is valid per the state machine."""
        return new_status in REFUND_STATE_TRANSITIONS.get(self.status, [])

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATES

    @property
    def effective_amount(self) -> float:
        """The approved amount if set, otherwise the requested amount."""
        return self.approved_amount if self.approved_amount is not None else self.amount


from app.models.order import Order  # noqa: E402, F401
from app.models.payment import Payment  # noqa: E402, F401
from app.models.refund_event import RefundEvent  # noqa: E402, F401
