"""Buyer Service — Orchestrates discovery, matching, and requirement parsing."""

import uuid
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.merchant import BuyerRequest, Merchant
from app.models.product import Product
from app.models.user import User, BuyerProfile
from app.schemas.buyer import (
    StructuredRequirements,
    BuyerRequestResponse,
    ProductScore,
    CompareResponse,
    SpendingPassport,
)
from app.agents.llm_provider import LLMProvider
from app.services.matching_engine import MatchingEngine
from app.audit.audit_service import AuditService
from app.repositories.merchant_repo import MerchantRepository, ProductRepository
from app.repositories.user_repo import UserRepository


class BuyerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMProvider()
        self.matching_engine = MatchingEngine()
        self.audit = AuditService(db)
        self.merchant_repo = MerchantRepository(db)
        self.product_repo = ProductRepository(db)
        self.user_repo = UserRepository(db)

    async def process_request(self, raw_request: str, user_id: str = "demo-user-001") -> BuyerRequestResponse:
        session_id = str(uuid.uuid4())
        start_time = time.time()

        # 1. Log request received
        await self.audit.log_action(
            session_id=session_id,
            actor="user",
            action="request_submitted",
            reason=f"User submitted: {raw_request}",
            metadata={"raw_request": raw_request, "user_id": user_id}
        )

        # 2. Extract structured requirements via LLM or deterministic fallback
        requirements, used_fallback, provider_name = await self.llm.extract_requirements(raw_request)
        duration_ms = int((time.time() - start_time) * 1000)

        # 3. Log agent action
        await self.audit.log_agent_action(
            session_id=session_id,
            agent_type="buyer_agent",
            action_type="parse_requirements",
            input_data={"raw_request": raw_request},
            output_data=requirements.model_dump(),
            status="success",
            duration_ms=duration_ms
        )

        # 4. Save to DB
        buyer_req = BuyerRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            raw_request=raw_request,
            structured_requirements=requirements.model_dump(),
            status="analyzed"
        )
        self.db.add(buyer_req)
        await self.db.commit()

        return BuyerRequestResponse(
            id=buyer_req.id,
            session_id=session_id,
            raw_request=raw_request,
            structured_requirements=requirements,
            status="analyzed",
            created_at=buyer_req.created_at
        )

    async def search_and_compare(
        self, session_id: str, requirements: StructuredRequirements, user_id: str = "demo-user-001"
    ) -> CompareResponse:
        start_time = time.time()

        # 1. Discover all active merchants & products
        merchants = await self.merchant_repo.get_active_merchants()
        products = await self.product_repo.get_active_products_by_category(requirements.category)

        # Merchant policy map
        merchant_policies = {
            m.id: {
                "max_discount_percent": m.policy.max_discount_percent if m.policy else 0,
                "negotiation_enabled": m.policy.negotiation_enabled if m.policy else False,
                "min_order_value": m.policy.min_order_value if m.policy else 0,
                "auto_discount_percent": m.policy.auto_discount_percent if m.policy else 0,
            }
            for m in merchants
        }

        # Format product dictionaries for matching engine
        merchant_name_map = {m.id: m.name for m in merchants}
        product_dicts = []
        for p in products:
            product_dicts.append({
                "id": p.id,
                "merchant_id": p.merchant_id,
                "merchant_name": merchant_name_map.get(p.merchant_id, "Unknown"),
                "name": p.name,
                "description": p.description or "",
                "category": p.category,
                "price": p.price,
                "currency": p.currency,
                "stock": p.stock,
                "rating": p.rating,
                "delivery_days": p.delivery_days,
                "specifications": p.specifications or {},
                "active": p.active,
            })

        # 2. Hard constraint filtering
        passing_products, filter_reasons = self.matching_engine.filter_products(
            product_dicts, requirements
        )

        # 3. Deterministic ranking
        ranked_scores = self.matching_engine.rank_products(
            passing_products, requirements, merchant_policies
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 4. Log agent discovery and matching action
        await self.audit.log_agent_action(
            session_id=session_id,
            agent_type="matching_engine",
            action_type="filter_and_rank",
            input_data={"total_products": len(product_dicts), "requirements": requirements.model_dump()},
            output_data={
                "qualifying_count": len(ranked_scores),
                "top_product": ranked_scores[0].product_name if ranked_scores else None,
                "top_score": ranked_scores[0].total_score if ranked_scores else None,
            },
            status="success",
            duration_ms=duration_ms
        )

        await self.audit.log_action(
            session_id=session_id,
            actor="matching_engine",
            action="products_filtered_and_ranked",
            reason=f"Found {len(ranked_scores)} qualifying products out of {len(product_dicts)} searched across {len(merchants)} merchants.",
            metadata={"qualifying_count": len(ranked_scores), "filter_reasons": filter_reasons}
        )

        explanation = None
        if ranked_scores:
            top = ranked_scores[0]
            explanation = (
                f"Top pick '{top.product_name}' from {top.merchant_name} scored {top.total_score}/100. "
                f"It meets all criteria with {top.delivery_days}-day delivery, price of Rs.{top.price:,.0f}, and rating of {top.rating}★."
            )

        return CompareResponse(
            session_id=session_id,
            total_products_searched=len(product_dicts),
            products_after_filtering=len(passing_products),
            qualifying_products=ranked_scores,
            filtered_out_reasons=filter_reasons,
            ai_explanation=explanation,
            used_deterministic_fallback=False
        )

    async def get_spending_passport(self, user_id: str = "demo-user-001") -> Optional[SpendingPassport]:
        profile = await self.user_repo.get_buyer_profile(user_id)
        user = await self.user_repo.get_by_id(user_id)
        if not profile or not user:
            return None

        categories = profile.allowed_categories.get("categories", []) if isinstance(profile.allowed_categories, dict) else []
        return SpendingPassport(
            user_id=user.id,
            user_name=user.name,
            single_transaction_limit=profile.single_transaction_limit,
            daily_spending_limit=profile.daily_spending_limit,
            daily_spent=profile.daily_spent,
            daily_remaining=max(0.0, profile.daily_spending_limit - profile.daily_spent),
            requires_approval_above=profile.requires_approval_above,
            allowed_categories=categories,
            status=profile.status,
            max_ai_discount_authority=2000.0,
        )
