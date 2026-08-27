"""Pydantic schemas for merchant-related requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MerchantResponse(BaseModel):
    """Merchant details response."""
    id: str
    name: str
    description: Optional[str] = None
    category: str
    trust_score: float
    status: str
    product_count: int = 0
    policy: Optional["MerchantPolicyResponse"] = None


class MerchantPolicyResponse(BaseModel):
    """Merchant policy details."""
    max_discount_percent: float
    min_order_value: float
    negotiation_enabled: bool
    requires_merchant_approval_above: float
    auto_discount_percent: float


class ProductResponse(BaseModel):
    """Product details response."""
    id: str
    merchant_id: str
    name: str
    description: Optional[str] = None
    category: str
    price: float
    currency: str = "INR"
    stock: int
    rating: float
    delivery_days: int
    specifications: Optional[dict] = None
    active: bool = True


class QuoteRequest(BaseModel):
    """Request a quote from a merchant."""
    product_id: str
    session_id: str
    request_discount: bool = Field(default=True, description="Whether to request a discount")


class QuoteResponse(BaseModel):
    """Quote from a merchant agent."""
    id: str
    merchant_id: str
    merchant_name: str
    product_id: str
    product_name: str
    original_price: float
    discount_percent: float
    discount_amount: float
    final_price: float
    valid_until: datetime
    status: str
    policy_check: dict = Field(default_factory=dict, description="Policy validation result")


class NegotiateRequest(BaseModel):
    """Negotiation request."""
    quote_id: str
    session_id: str
    requested_discount_percent: Optional[float] = Field(None, description="Specific discount % to request")
    negotiation_message: Optional[str] = Field(None, description="Optional negotiation message")


class NegotiateResponse(BaseModel):
    """Negotiation result."""
    quote_id: str
    original_price: float
    requested_discount_percent: float
    approved_discount_percent: float
    final_price: float
    status: str  # approved, rejected, counter_offer
    merchant_message: str
    policy_validation: dict
    negotiation_steps: list[dict] = Field(default_factory=list)
