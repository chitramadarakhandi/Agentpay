"""Pydantic schemas for buyer-related requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BuyerRequestCreate(BaseModel):
    """Schema for submitting a natural-language shopping request."""
    raw_request: str = Field(..., min_length=5, max_length=1000, description="Natural language shopping request")
    user_id: str = Field(default="demo-user-001", description="User ID")


class StructuredRequirements(BaseModel):
    """Deterministic structured requirements extracted from user request."""
    category: str = Field(default="laptops", description="Product category")
    budget_max: Optional[float] = Field(None, description="Maximum budget in INR")
    budget_min: Optional[float] = Field(None, description="Minimum budget in INR")
    minimum_ram_gb: Optional[int] = Field(None, description="Minimum RAM in GB")
    minimum_storage_gb: Optional[int] = Field(None, description="Minimum storage in GB")
    maximum_delivery_days: Optional[int] = Field(None, description="Maximum delivery days")
    purpose: Optional[str] = Field(None, description="Intended use case")
    preferred_brands: Optional[list[str]] = Field(None, description="Preferred brands")
    required_features: Optional[list[str]] = Field(None, description="Required features list")
    preferred_os: Optional[str] = Field(None, description="Preferred operating system")


class BuyerRequestResponse(BaseModel):
    """Response after processing a buyer request."""
    id: str
    session_id: str
    raw_request: str
    structured_requirements: Optional[StructuredRequirements] = None
    status: str
    created_at: datetime


class SearchRequest(BaseModel):
    """Schema for product search."""
    session_id: str = Field(..., description="Session ID from buyer request")
    requirements: StructuredRequirements
    user_id: str = Field(default="demo-user-001")


class ProductScore(BaseModel):
    """Product with ranking score breakdown."""
    product_id: str
    merchant_id: str
    merchant_name: str
    product_name: str
    description: str
    price: float
    currency: str
    rating: float
    delivery_days: int
    stock: int
    specifications: dict
    
    # Score breakdown (transparent ranking)
    total_score: float = Field(description="Overall ranking score 0-100")
    requirement_match_score: float = Field(description="How well it matches requirements (30%)")
    price_value_score: float = Field(description="Price competitiveness (20%)")
    rating_score: float = Field(description="Product rating quality (15%)")
    specification_score: float = Field(description="Spec quality beyond minimums (15%)")
    delivery_score: float = Field(description="Delivery speed (10%)")
    discount_potential_score: float = Field(description="Potential discount from merchant (10%)")
    
    meets_all_requirements: bool = Field(description="Whether ALL hard constraints pass")
    recommendation_reasons: list[str] = Field(description="Human-readable reasons for recommendation")


class CompareResponse(BaseModel):
    """Response with ranked product comparison."""
    session_id: str
    total_products_searched: int
    products_after_filtering: int
    qualifying_products: list[ProductScore]
    filtered_out_reasons: dict = Field(default_factory=dict, description="Count of products filtered per reason")
    ai_explanation: Optional[str] = Field(None, description="AI-generated explanation (if LLM available)")
    used_deterministic_fallback: bool = Field(default=False)


class SpendingPassport(BaseModel):
    """Buyer's AI Spending Passport — limits and permissions."""
    user_id: str
    user_name: str
    single_transaction_limit: float
    daily_spending_limit: float
    daily_spent: float
    daily_remaining: float
    requires_approval_above: float
    allowed_categories: list[str]
    status: str
    max_ai_discount_authority: float = Field(default=2000.0, description="Max discount AI can auto-approve")
