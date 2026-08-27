"""RefundEvent and WebhookEvent models for audit trail and webhook deduplication."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class RefundEvent(Base):
    """Immutable event log for each step in a refund lifecycle."""
    __tablename__ = "refund_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    refund_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("refunds.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # refund_requested, eligibility_checked, merchant_recommended, approval_pending,
       # refund_approved, refund_rejected, refund_processing, refund_processed,
       # refund_failed, webhook_received, refund_retried
    actor: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # buyer_agent, policy_engine, merchant_agent, merchant, refund_service, razorpay, webhook, system
    status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # mirrors refund status at time of event
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    refund: Mapped["Refund"] = relationship(back_populates="events")


class WebhookEvent(Base):
    """Stores incoming webhook events for deduplication and audit."""
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="razorpay"
    )  # razorpay
    event_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # refund.processed, refund.failed, refund.created, etc.
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


from app.models.refund import Refund  # noqa: E402, F401
