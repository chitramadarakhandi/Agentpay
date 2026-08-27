"""Pydantic schemas for payments."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    """Request to create a Razorpay payment order."""
    order_id: str


class PaymentCreateResponse(BaseModel):
    """Response with Razorpay order details for frontend checkout."""
    payment_id: str
    order_id: str
    razorpay_order_id: str
    razorpay_key_id: str  # Public key, safe for frontend
    amount: int  # Amount in paise
    currency: str = "INR"
    merchant_name: str
    product_name: str


class PaymentVerifyRequest(BaseModel):
    """Payment verification request with Razorpay callback data."""
    order_id: str
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str


class PaymentVerifyResponse(BaseModel):
    """Payment verification result."""
    order_id: str
    payment_id: str
    status: str  # success, failed
    amount: float
    message: str
    verified: bool
    already_processed: bool = False


class PaymentFailureResponse(BaseModel):
    """Payment failure details."""
    order_id: str
    status: str = "failed"
    failure_reason: str
    can_retry: bool = True
    message: str
