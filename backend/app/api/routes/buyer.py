"""Buyer routes — fully wired with BuyerService."""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_db
from app.services.buyer_service import BuyerService
from app.schemas.buyer import StructuredRequirements

router = APIRouter()


class BuyerRequestBody(BaseModel):
    raw_request: str
    user_id: str = "demo-user-001"


class SearchBody(BaseModel):
    session_id: str
    requirements: StructuredRequirements
    user_id: str = "demo-user-001"


class FullFlowBody(BaseModel):
    """Single-call endpoint: parse + search + compare in one shot for demo."""
    raw_request: str
    user_id: str = "demo-user-001"


@router.post("/requests")
async def create_buyer_request(body: BuyerRequestBody, db: AsyncSession = Depends(get_db)):
    """Submit natural-language request → extract structured requirements."""
    svc = BuyerService(db)
    result = await svc.process_request(body.raw_request, body.user_id)
    return result


@router.post("/search")
async def search_products(body: SearchBody, db: AsyncSession = Depends(get_db)):
    """Filter + rank products across all merchants using structured requirements."""
    svc = BuyerService(db)
    result = await svc.search_and_compare(body.session_id, body.requirements, body.user_id)
    return result


@router.post("/flow")
async def full_buyer_flow(body: FullFlowBody, db: AsyncSession = Depends(get_db)):
    """
    One-shot demo endpoint: parse request → filter → rank → return top picks.
    Returns both the parsed requirements AND ranked products.
    """
    svc = BuyerService(db)
    # Step 1: Parse
    req_result = await svc.process_request(body.raw_request, body.user_id)
    if not req_result.structured_requirements:
        raise HTTPException(status_code=422, detail="Could not extract requirements from request.")
    # Step 2: Search + Rank
    compare_result = await svc.search_and_compare(
        req_result.session_id,
        req_result.structured_requirements,
        body.user_id,
    )
    return {
        "session_id": req_result.session_id,
        "raw_request": body.raw_request,
        "requirements": req_result.structured_requirements,
        "results": compare_result,
    }


@router.get("/passport")
async def get_passport(user_id: str = "demo-user-001", db: AsyncSession = Depends(get_db)):
    """Get the buyer's AI Spending Passport."""
    svc = BuyerService(db)
    passport = await svc.get_spending_passport(user_id)
    if not passport:
        raise HTTPException(status_code=404, detail="Buyer profile not found.")
    return passport
