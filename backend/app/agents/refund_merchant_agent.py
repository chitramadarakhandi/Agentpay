"""AI Merchant Agent for refund recommendation.

Evaluates refund requests and makes a recommendation:
  APPROVE_FULL, APPROVE_PARTIAL, REJECT

CRITICAL: The Merchant Agent CANNOT bypass the deterministic policy engine.
If the policy engine says ineligible, the merchant agent MUST recommend rejection.
"""

import json
import re
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("agentpay.refund_merchant_agent")


MERCHANT_SYSTEM_PROMPT = """You are an AI Merchant Agent for AgentPay evaluating a refund request.
You have been provided the refund details and the deterministic policy evaluation.

CRITICAL RULES:
1. If the policy engine says the refund is INELIGIBLE, you MUST recommend REJECT.
2. You cannot override the policy engine's decision.
3. Your role is to provide nuanced reasoning within policy bounds.

Based on the policy evaluation and refund details, respond with ONLY valid JSON:
{
  "recommendation": "APPROVE_FULL" | "APPROVE_PARTIAL" | "REJECT",
  "approved_amount": number | null,
  "reasoning": string,
  "confidence": number (0.0 to 1.0)
}

If recommending APPROVE_PARTIAL, set approved_amount to the recommended amount.
If recommending APPROVE_FULL or REJECT, set approved_amount to null.
"""


class MerchantRecommendation(BaseModel):
    """Validated merchant recommendation for a refund."""
    recommendation: str = Field(
        ..., description="APPROVE_FULL, APPROVE_PARTIAL, or REJECT"
    )
    approved_amount: Optional[float] = Field(
        None, description="Amount to approve for partial refund"
    )
    reasoning: str = Field(..., description="Human-readable reasoning")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in recommendation"
    )


class RefundMerchantAgent:
    """AI Merchant Agent that recommends refund decisions."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.gemini_key = settings.gemini_api_key
        self.groq_key = settings.groq_api_key
        self.openai_key = settings.openai_api_key

    async def recommend(
        self,
        refund_reason: str,
        reason_category: str,
        requested_amount: float,
        policy_result: dict[str, Any],
        product_name: str = "",
        product_category: str = "",
    ) -> tuple[MerchantRecommendation, bool, str]:
        """Generate a refund recommendation.

        Returns:
            (MerchantRecommendation, used_fallback: bool, provider_name: str)
        """
        eligible = policy_result.get("eligible", False)

        # Build context for LLM
        context = (
            f"Product: {product_name} ({product_category})\n"
            f"Refund reason: {refund_reason}\n"
            f"Reason category: {reason_category}\n"
            f"Requested amount: ₹{requested_amount:,.2f}\n"
            f"Policy eligible: {eligible}\n"
            f"Policy decision: {policy_result.get('decision_reason', '')}\n"
            f"Policy checks: {json.dumps(policy_result.get('checks', []))}\n"
        )

        if self.provider == "gemini" and self.gemini_key:
            try:
                result = await self._call_gemini(context, eligible)
                if result:
                    return self._enforce_policy(result, eligible, requested_amount), False, "gemini"
            except Exception as e:
                logger.warning(f"Gemini call failed: {e}. Falling back.")

        elif self.provider == "groq" and self.groq_key:
            try:
                result = await self._call_groq(context, eligible)
                if result:
                    return self._enforce_policy(result, eligible, requested_amount), False, "groq"
            except Exception as e:
                logger.warning(f"Groq call failed: {e}. Falling back.")

        elif self.provider == "openai" and self.openai_key:
            try:
                result = await self._call_openai(context, eligible)
                if result:
                    return self._enforce_policy(result, eligible, requested_amount), False, "openai"
            except Exception as e:
                logger.warning(f"OpenAI call failed: {e}. Falling back.")

        return self.deterministic_recommendation(
            eligible, refund_reason, reason_category, requested_amount, policy_result
        ), True, "deterministic_rule_engine"

    def _enforce_policy(
        self, rec: MerchantRecommendation, eligible: bool, requested_amount: float
    ) -> MerchantRecommendation:
        """CRITICAL: Ensure LLM recommendation does not bypass policy engine."""
        if not eligible and rec.recommendation != "REJECT":
            logger.warning(
                f"[MerchantAgent] LLM recommended {rec.recommendation} but policy says ineligible. "
                "Overriding to REJECT."
            )
            rec.recommendation = "REJECT"
            rec.reasoning = "Refund cannot be approved. Policy engine determined ineligibility."
            rec.approved_amount = None

        # Ensure approved_amount doesn't exceed requested
        if rec.approved_amount is not None and rec.approved_amount > requested_amount:
            rec.approved_amount = requested_amount

        return rec

    async def _call_gemini(self, context: str, eligible: bool) -> Optional[MerchantRecommendation]:
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(
            f"{MERCHANT_SYSTEM_PROMPT}\n\n{context}"
        )
        return self._parse_json(response.text.strip())

    async def _call_groq(self, context: str, eligible: bool) -> Optional[MerchantRecommendation]:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=self.groq_key)
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": MERCHANT_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        return self._parse_json(completion.choices[0].message.content)

    async def _call_openai(self, context: str, eligible: bool) -> Optional[MerchantRecommendation]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.openai_key,
            base_url=settings.openai_base_url or None,
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": MERCHANT_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            response_format={"type": "json_object"},
        )
        return self._parse_json(response.choices[0].message.content)

    def _parse_json(self, text: str) -> Optional[MerchantRecommendation]:
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text.strip())
        return MerchantRecommendation(**data)

    def deterministic_recommendation(
        self,
        eligible: bool,
        reason: str,
        reason_category: str,
        requested_amount: float,
        policy_result: dict[str, Any],
    ) -> MerchantRecommendation:
        """Deterministic recommendation based on policy and reason category."""
        if not eligible:
            return MerchantRecommendation(
                recommendation="REJECT",
                approved_amount=None,
                reasoning=f"Refund cannot be approved. {policy_result.get('decision_reason', 'Policy check failed.')}",
                confidence=1.0,
            )

        # For clear-cut reasons, recommend full refund
        if reason_category in ("damaged", "defective", "wrong_item"):
            return MerchantRecommendation(
                recommendation="APPROVE_FULL",
                approved_amount=None,
                reasoning=f"Refund recommended: {reason_category.replace('_', ' ').title()} products are eligible for full refund under merchant policy.",
                confidence=0.95,
            )

        if reason_category == "not_as_described":
            return MerchantRecommendation(
                recommendation="APPROVE_FULL",
                approved_amount=None,
                reasoning="Product not as described — full refund recommended to maintain customer satisfaction.",
                confidence=0.90,
            )

        if reason_category == "changed_mind":
            return MerchantRecommendation(
                recommendation="APPROVE_FULL",
                approved_amount=None,
                reasoning="Change of mind refund — eligible within the return window. Full refund recommended.",
                confidence=0.85,
            )

        if reason_category == "late_delivery":
            return MerchantRecommendation(
                recommendation="APPROVE_FULL",
                approved_amount=None,
                reasoning="Late delivery — full refund recommended for service quality.",
                confidence=0.88,
            )

        # Default: approve full
        return MerchantRecommendation(
            recommendation="APPROVE_FULL",
            approved_amount=None,
            reasoning="Refund request meets all policy criteria. Full refund recommended.",
            confidence=0.80,
        )
