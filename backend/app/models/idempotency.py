"""Idempotency Record model for distributed transaction safety with TTL."""

import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def default_idempotency_expiry():
    # 24 hours validity
    return datetime.now(timezone.utc) + timedelta(hours=24)


class IdempotencyRecord(Base):
    """Stores request fingerprints, status, and cached responses to prevent duplicate execution."""

    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )  # PENDING, COMPLETED, FAILED
    response_code: Mapped[int] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=default_idempotency_expiry, index=True
    )
