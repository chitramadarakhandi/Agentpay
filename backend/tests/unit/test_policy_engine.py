"""Unit tests for Trust & Policy Engine."""

import pytest
from app.policies.trust_engine import TrustEngine


@pytest.fixture
def trust_engine():
    return TrustEngine()


@pytest.fixture
def buyer_profile():
    return {
        "single_transaction_limit": 80000.0,
        "daily_spending_limit": 150000.0,
        "daily_spent": 20000.0,
        "requires_approval_above": 50000.0,
        "allowed_categories": {"categories": ["electronics", "laptops", "phones"]},
        "status": "active",
    }


@pytest.fixture
def merchant_policy():
    return {
        "max_discount_percent": 15.0,
        "negotiation_enabled": True,
        "min_order_value": 1000.0,
        "requires_merchant_approval_above": 100000.0,
    }


@pytest.fixture
def valid_product():
    return {
        "id": "prod-1",
        "name": "Pro Laptop",
        "category": "laptops",
        "price": 60000.0,
        "stock": 5,
        "active": True,
    }


def test_transaction_within_limits_passes(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test valid transaction passing all policy checks."""
    result = trust_engine.evaluate_transaction(
        amount=60000.0,
        discount_percent=10.0,
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is True
    # 60000 > requires_approval_above (50000), so requires user approval
    assert result.requires_user_approval is True


def test_exceeding_single_transaction_limit_blocks(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test that exceeding single transaction limit blocks purchase."""
    result = trust_engine.evaluate_transaction(
        amount=95000.0,  # Exceeds 80,000 limit
        discount_percent=5.0,
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is False
    assert any("single transaction limit" in r.lower() for r in result.reasons)


def test_exceeding_daily_spending_limit_blocks(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test that exceeding remaining daily budget blocks purchase."""
    buyer_profile["daily_spent"] = 120000.0  # Remaining is 30,000
    result = trust_engine.evaluate_transaction(
        amount=40000.0,  # 120,000 + 40,000 > 150,000
        discount_percent=5.0,
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is False
    assert any("daily" in r.lower() for r in result.reasons)


def test_restricted_category_blocks(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test that forbidden category blocks purchase."""
    valid_product["category"] = "furniture"  # Not in allowed list
    result = trust_engine.evaluate_transaction(
        amount=30000.0,
        discount_percent=5.0,
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is False
    assert any("category" in r.lower() for r in result.reasons)


def test_excessive_discount_blocks(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test that requesting discount exceeding merchant policy blocks purchase."""
    result = trust_engine.evaluate_transaction(
        amount=50000.0,
        discount_percent=25.0,  # Exceeds merchant max 15.0%
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is False
    assert any("discount" in r.lower() for r in result.reasons)


def test_out_of_stock_product_blocks(trust_engine, buyer_profile, merchant_policy, valid_product):
    """Test that zero-stock product blocks purchase."""
    valid_product["stock"] = 0
    result = trust_engine.evaluate_transaction(
        amount=50000.0,
        discount_percent=5.0,
        buyer_profile=buyer_profile,
        merchant_policy=merchant_policy,
        product=valid_product,
        session_id="sess-1",
    )
    assert result.allowed is False
    assert any("out of stock" in r.lower() for r in result.reasons)
