"""Unit tests for Multi-Agent Collusion & Boundary-Probing Anomaly Detection."""

import pytest
from app.services.negotiation_engine import NegotiationEngine
from app.policies.collusion_detector import CollusionDetector


def test_excessive_negotiation_attempts_triggers_lockout():
    """Test that more than 3 negotiation rounds on the same quote triggers security lockout."""
    detector = CollusionDetector(max_attempts_per_session=3)
    session_id = "sess_probe_01"
    quote_id = "quote_probe_01"

    # Attempt 1, 2, 3 pass anomaly check
    assert detector.evaluate_negotiation_attempt(session_id, quote_id, 5.0)[0] is False
    assert detector.evaluate_negotiation_attempt(session_id, quote_id, 8.0)[0] is False
    assert detector.evaluate_negotiation_attempt(session_id, quote_id, 10.0)[0] is False

    # 4th attempt trips collusion/exhaustion detector
    is_suspicious, reason = detector.evaluate_negotiation_attempt(session_id, quote_id, 12.0)
    assert is_suspicious is True
    assert "Excessive negotiation attempts" in reason


def test_step_probing_boundary_extraction_attack_detected():
    """Test detection of fine-grained incremental stepping (probing the policy ceiling)."""
    detector = CollusionDetector(max_attempts_per_session=5, step_probing_threshold=3)
    session_id = "sess_probe_02"
    quote_id = "quote_probe_02"

    # Systematic fine-grained increments: 10% -> 11% -> 12%
    detector.evaluate_negotiation_attempt(session_id, quote_id, 10.0)
    detector.evaluate_negotiation_attempt(session_id, quote_id, 11.0)
    is_suspicious, reason = detector.evaluate_negotiation_attempt(session_id, quote_id, 12.0)

    assert is_suspicious is True
    assert "Automated boundary-probing attack detected" in reason


def test_negotiation_engine_halts_on_collusion_attack():
    """Verify NegotiationEngine returns security violation status on probe attack."""
    engine = NegotiationEngine()
    policy = {"max_discount_percent": 15.0, "auto_discount_percent": 5.0, "negotiation_enabled": True}
    session = "sess_eng_probe"
    quote = "quote_eng_probe"

    # Run 4 successive attempts
    engine.negotiate(10000, 5.0, policy, "MerchantA", session_id=session, quote_id=quote)
    engine.negotiate(10000, 8.0, policy, "MerchantA", session_id=session, quote_id=quote)
    engine.negotiate(10000, 10.0, policy, "MerchantA", session_id=session, quote_id=quote)
    
    # 4th attempt should be blocked with collusion_detected=True
    res = engine.negotiate(10000, 12.0, policy, "MerchantA", session_id=session, quote_id=quote)
    assert res.approved is False
    assert res.collusion_detected is True
    assert "Negotiation locked" in res.merchant_message
