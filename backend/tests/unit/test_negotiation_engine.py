"""Unit tests for Negotiation Engine."""

import pytest
from app.services.negotiation_engine import NegotiationEngine


@pytest.fixture
def negotiation_engine():
    return NegotiationEngine()


@pytest.fixture
def standard_policy():
    return {
        "max_discount_percent": 15.0,
        "auto_discount_percent": 5.0,
        "negotiation_enabled": True,
    }


def test_negotiation_within_bounds_is_approved(negotiation_engine, standard_policy):
    """Discount within merchant policy is approved."""
    result = negotiation_engine.negotiate(
        original_price=10000.0,
        requested_discount_percent=10.0,
        merchant_policy=standard_policy,
        merchant_name="TechStore",
    )
    assert result.approved is True
    assert result.approved_discount_percent == 10.0
    assert result.discount_amount == 1000.0
    assert result.final_price == 9000.0
    assert result.policy_validation["blocked"] is False


def test_excessive_negotiation_is_countered_with_max(negotiation_engine, standard_policy):
    """Discount exceeding merchant policy is bounded and countered with max allowed."""
    result = negotiation_engine.negotiate(
        original_price=10000.0,
        requested_discount_percent=25.0,  # Exceeds max 15.0%
        merchant_policy=standard_policy,
        merchant_name="TechStore",
    )
    assert result.approved is True
    assert result.approved_discount_percent == 15.0  # Capped at max
    assert result.final_price == 8500.0
    assert result.policy_validation["blocked"] is True
    assert result.policy_validation["counter_offered"] is True


def test_disabled_negotiation_falls_back_to_auto_discount(negotiation_engine):
    """When negotiation is disabled, applies auto-discount if configured."""
    policy = {
        "max_discount_percent": 10.0,
        "auto_discount_percent": 3.0,
        "negotiation_enabled": False,
    }
    result = negotiation_engine.negotiate(
        original_price=20000.0,
        requested_discount_percent=8.0,
        merchant_policy=policy,
        merchant_name="FixedPriceStore",
    )
    assert result.approved_discount_percent == 3.0
    assert result.final_price == 19400.0
