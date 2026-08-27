"""Refund API schemas — Pydantic validated request/response models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────

class RefundCreateRequest(BaseModel):
    """Direct refund request with structured fields."""
    order_id: str
    payment_id: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    reason: str = Field(min_length=1, max_length=500)


class RefundNLPRequest(BaseModel):
    """Natural language refund request — AI buyer agent extracts structure."""
    message: str = Field(min_length=3, max_length=2000, description="Natural language refund request")
    order_id: Optional[str] = Field(None, description="Optional order ID if known")
    user_id: str = Field(default="demo-user-001")


class RefundApproveRequest(BaseModel):
    """Merchant approval of a refund."""
    approved_amount: Optional[float] = Field(None, gt=0, description="Partial refund amount. Null = full approved amount.")
    merchant_note: Optional[str] = Field(None, max_length=500)


class RefundRejectRequest(BaseModel):
    """Merchant rejection of a refund."""
    rejection_reason: str = Field(min_length=1, max_length=500)


# ── Response schemas ──────────────────────────────────────────

class RefundEventResponse(BaseModel):
    """A single event in the refund timeline."""
    id: str
    event_type: str
    actor: str
    status: str
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class EligibilityCheckItem(BaseModel):
    """Single eligibility check verdict."""
    check_id: str
    label: str
    passed: bool
    detail: str


class EligibilityResponse(BaseModel):
    """Full eligibility evaluation with individual check verdicts."""
    eligible: bool
    decision: str
    decision_reason: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    product_id: Optional[str] = None
    product_name: str = "Unknown product"
    category: str = "general"
    merchant_id: Optional[str] = None
    amount_paid: float = 0
    refunded_amount: float = 0
    remaining_refundable_amount: float = 0
    currency: str = "INR"
    policy: dict = Field(default_factory=dict)
    checks: list[EligibilityCheckItem] = Field(default_factory=list)


class RefundResponse(BaseModel):
    """Refund detail response."""
    id: str
    order_id: str
    payment_id: str
    buyer_id: str
    merchant_id: str
    amount: float
    approved_amount: Optional[float] = None
    currency: str
    reason: str
    refund_type: str
    status: str
    gateway_refund_id: Optional[str] = None
    failure_reason: Optional[str] = None
    policy_result: Optional[dict[str, Any]] = None
    ai_recommendation: Optional[dict[str, Any]] = None
    refunded_amount: float
    remaining_refundable_amount: float
    events: list[RefundEventResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RefundListResponse(BaseModel):
    """List of refunds for an order."""
    order_id: str
    refunds: list[RefundResponse]
    count: int


class RefundDashboardResponse(BaseModel):
    """Merchant refund dashboard aggregates."""
    total_refunds: int = 0
    pending_approval: int = 0
    approved: int = 0
    processing: int = 0
    completed: int = 0
    rejected: int = 0
    failed: int = 0
    total_refunded_amount: float = 0
    refunds: list[RefundResponse] = Field(default_factory=list)


class NLPExtractionResponse(BaseModel):
    """Response from NLP refund extraction."""
    extraction: dict[str, Any]
    used_fallback: bool
    provider: str
    eligibility: Optional[EligibilityResponse] = None
    refund: Optional[RefundResponse] = None
