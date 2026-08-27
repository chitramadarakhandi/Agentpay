"""Normalized kill-chain behavior tests."""

import pytest

from app.audit.audit_service import AuditService
from app.models.audit import AuditLog


@pytest.mark.asyncio
async def test_successful_chain_marks_reached_stages_passed(db_session):
    db_session.add_all([
        AuditLog(session_id="chain-ok", actor="buyer_agent", action="request_submitted"),
        AuditLog(session_id="chain-ok", actor="payment_service", action="payment_intent_created"),
        AuditLog(session_id="chain-ok", actor="payment_service", action="payment_verified_and_settled"),
    ])
    await db_session.commit()
    chain = await AuditService(db_session).get_session_chain("chain-ok")
    assert chain["status"] == "passed"
    assert chain["stopping_stage"] is None
    assert chain["stages"][-1]["status"] == "passed"


@pytest.mark.asyncio
async def test_blocked_policy_stops_later_stages(db_session):
    db_session.add(AuditLog(
        session_id="chain-blocked", actor="policy_engine", action="policy_blocked",
        reason="Discount exceeds maximum.", policy_result={"blocked": True},
    ))
    await db_session.commit()
    chain = await AuditService(db_session).get_session_chain("chain-blocked")
    assert chain["status"] == "blocked"
    assert chain["stopping_stage"] == "policy"
    assert chain["stages"][7]["status"] == "unreached"


@pytest.mark.asyncio
async def test_pending_approval_is_waiting_state(db_session):
    db_session.add(AuditLog(
        session_id="chain-pending", actor="order_service", action="order_pending_approval",
        reason="Human approval required.", approval_status="pending",
    ))
    await db_session.commit()
    chain = await AuditService(db_session).get_session_chain("chain-pending")
    assert chain["status"] == "pending"
    assert chain["stopping_stage"] == "approval"
