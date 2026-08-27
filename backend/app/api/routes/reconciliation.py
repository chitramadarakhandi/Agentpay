"""Reconciliation API routes — cross-checks, settlement reports, and money conservation invariant checks."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.reconciliation_service import ReconciliationService

router = APIRouter()


@router.post("/run")
async def run_reconciliation(
    lookback_hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
    auto_heal: bool = Query(True, description="Automatically heal missed webhooks"),
    db: AsyncSession = Depends(get_db),
):
    """Run on-demand reconciliation batch comparing DB state, internal payment logs, and Gateway status."""
    recon_svc = ReconciliationService(db)
    report = await recon_svc.run_reconciliation(
        lookback_hours=lookback_hours,
        auto_heal=auto_heal,
    )
    return report


@router.get("/status")
async def get_reconciliation_status(db: AsyncSession = Depends(get_db)):
    """Get the latest reconciliation health status."""
    recon_svc = ReconciliationService(db)
    report = await recon_svc.run_reconciliation(lookback_hours=24, auto_heal=False)
    return {
        "status": "operational",
        "last_health_score": report["health_score_percent"],
        "pending_discrepancies": report["discrepancies_flagged"],
        "summary": report,
    }


@router.get("/invariant-check")
async def get_money_conservation_invariant(db: AsyncSession = Depends(get_db)):
    """
    Fintech Invariant Check — Double-entry conservation rule:
    Σ(Orders[status='success']) == Σ(Payments[status='success']) with zero drift (Δ = ₹0.00).
    """
    recon_svc = ReconciliationService(db)
    return await recon_svc.check_money_conservation_invariant()
