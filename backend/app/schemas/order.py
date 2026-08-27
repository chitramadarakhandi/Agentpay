"""Pydantic schemas for orders."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    """Create a new order."""
    quote_id: str
    session_id: str
    user_id: str = Field(default="demo-user-001")


class OrderResponse(BaseModel):
    """Order details response."""
    id: str
    buyer_id: str
    merchant_id: str
    product_id: str
    quote_id: Optional[str] = None
    session_id: str
    amount: float
    currency: str = "INR"
    status: str
    razorpay_order_id: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Enriched data
    product_name: Optional[str] = None
    merchant_name: Optional[str] = None
