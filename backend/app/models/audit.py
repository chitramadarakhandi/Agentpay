"""Audit trail models: AgentAction, AuditLog, PolicyViolation."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AgentAction(Base):
    """Records every action taken by an AI agent."""
    __tablename__ = "agent_actions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # buyer_agent, merchant_agent, discovery_agent, matching_engine, etc.
    action_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # parse_request, search_products, generate_quote, negotiate, etc.
    input_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )  # success, failed, timeout, blocked
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AuditLog(Base):
    """Immutable audit trail for all financially-relevant actions."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # buyer_agent, merchant_agent, policy_engine, payment_service, user
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # request_parsed, products_filtered, quote_generated, payment_created, etc.
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=True)
    policy_result: Mapped[dict] = mapped_column(JSON, nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=True
    )  # pending, approved, rejected, auto_approved
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class PolicyViolation(Base):
    """Records every time a policy blocks an action."""
    __tablename__ = "policy_violations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # spending_limit, discount_limit, category_restriction, etc.
    requested_value: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # low, medium, high, critical
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
