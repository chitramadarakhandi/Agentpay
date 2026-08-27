"""Pydantic schemas for audit trail."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Single audit log entry."""
    id: str
    session_id: str
    actor: str
    action: str
    reason: Optional[str] = None
    amount: Optional[float] = None
    policy_result: Optional[dict] = None
    approval_status: Optional[str] = None
    metadata_json: Optional[dict] = None
    timestamp: datetime


class AgentActionResponse(BaseModel):
    """Single agent action entry."""
    id: str
    session_id: str
    agent_type: str
    action_type: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    status: str
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime


class AuditTrailResponse(BaseModel):
    """Full audit trail for a session."""
    session_id: str
    audit_logs: list[AuditLogResponse]
    agent_actions: list[AgentActionResponse]
    policy_violations: list[dict]
    total_events: int


class PolicyEvaluationRequest(BaseModel):
    """Request to evaluate a transaction against policies."""
    user_id: str = Field(default="demo-user-001")
    merchant_id: str
    product_id: str
    amount: float
    discount_percent: float = 0.0
    session_id: str


class PolicyEvaluationResponse(BaseModel):
    """Result of policy evaluation."""
    allowed: bool
    requires_user_approval: bool
    reasons: list[str]
    checks: list[dict] = Field(default_factory=list, description="Individual policy check results")
    buyer_passport: Optional[dict] = None
    merchant_policy: Optional[dict] = None
