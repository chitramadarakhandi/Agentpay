"""Unit and integration tests for Policy Simulation and Explainability."""

import pytest
from app.models.order import Order
from sqlalchemy import select


@pytest.mark.asyncio
async def test_policy_simulation_does_not_persist_db_rows(client, db_session, seed_data):
    """Verify that POST /api/policy/simulate dry-runs without creating orders or payments in DB."""
    # Count orders before simulation
    count_before = len((await db_session.execute(select(Order))).scalars().all())

    sim_payload = {
        "user_id": "demo-user-001",
        "amount": 60000.0,
        "discount_percent": 10.0,
        "category": "laptops",
        "product_name": "Ultra Book Pro",
        "stock": 5,
        "session_id": "dry-run-sim-101",
    }

    res = await client.post("/api/policy/simulate", json=sim_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["simulation_mode"] is True
    assert data["allowed"] is True
    assert data["explainability_score"] == 1.0
    assert len(data["arithmetic_breakdown"]) > 0

    # Count orders after simulation: MUST BE ZERO CHANGE
    count_after = len((await db_session.execute(select(Order))).scalars().all())
    assert count_after == count_before


@pytest.mark.asyncio
async def test_policy_simulation_blocked_shows_arithmetic_deficit(client, seed_data):
    """Verify that blocked dry-run simulation shows precise arithmetic breakdown with deficit."""
    sim_payload = {
        "user_id": "demo-user-001",
        "amount": 120000.0,  # Exceeds 80,000 single transaction limit
        "discount_percent": 20.0,  # Exceeds 15% merchant limit
        "category": "laptops",
        "product_name": "Extreme Server",
        "stock": 2,
        "session_id": "dry-run-sim-102",
    }

    res = await client.post("/api/policy/simulate", json=sim_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["allowed"] is False
    # Check that arithmetic formula contains explicit deficit calculation
    breakdown_text = " ".join(data["arithmetic_breakdown"])
    assert "Deficit: ₹40,000.00" in breakdown_text
    assert "Excess: 5.0%" in breakdown_text
