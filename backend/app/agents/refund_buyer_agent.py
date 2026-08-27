"""AI Buyer Agent for refund request extraction.

Extracts structured refund requests from natural language using LLM
or deterministic regex fallback. Validates output with Pydantic.

Example input:
  "I want to return this laptop because it arrived damaged."

Example output:
  RefundRequestExtraction(order_id=None, reason="damaged", requested_amount=None, refund_type="full")
"""

import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


REFUND_SYSTEM_PROMPT = """You are an AI Buyer Agent refund request parser for AgentPay.
Extract structured refund information from the user's natural language request.
Return strictly valid JSON matching this schema:
{
  "order_id": string | null,
  "reason": string,
  "reason_category": "damaged" | "defective" | "wrong_item" | "not_as_described" | "changed_mind" | "late_delivery" | "other",
  "requested_amount": number | null,
  "refund_type": "full" | "partial"
}
Do NOT include markdown backticks or commentary, only raw JSON.
If the user mentions a specific order ID or number, extract it.
If no amount is specified, assume full refund (requested_amount = null).
"""


class RefundRequestExtraction(BaseModel):
    """Validated refund request extracted from natural language."""
    order_id: Optional[str] = Field(None, description="Extracted order ID if mentioned")
    reason: str = Field(..., min_length=1, max_length=500, description="Refund reason")
    reason_category: str = Field(
        default="other",
        description="Categorized reason: damaged, defective, wrong_item, not_as_described, changed_mind, late_delivery, other"
    )
    requested_amount: Optional[float] = Field(None, gt=0, description="Requested refund amount")
    refund_type: str = Field(default="full", description="full or partial")


class RefundBuyerAgent:
    """Extracts structured refund requests from natural language."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.gemini_key = settings.gemini_api_key
        self.groq_key = settings.groq_api_key
        self.openai_key = settings.openai_api_key

    async def extract_refund_request(self, raw_text: str) -> tuple[RefundRequestExtraction, bool, str]:
        """Extract structured refund request from natural text.

        Returns:
            (RefundRequestExtraction, used_fallback: bool, provider_name: str)
        """
        if self.provider == "gemini" and self.gemini_key:
            try:
                result = await self._call_gemini(raw_text)
                if result:
                    return result, False, "gemini"
            except Exception as e:
                print(f"[RefundBuyerAgent] Gemini call failed: {e}. Falling back.")

        elif self.provider == "groq" and self.groq_key:
            try:
                result = await self._call_groq(raw_text)
                if result:
                    return result, False, "groq"
            except Exception as e:
                print(f"[RefundBuyerAgent] Groq call failed: {e}. Falling back.")

        elif self.provider == "openai" and self.openai_key:
            try:
                result = await self._call_openai(raw_text)
                if result:
                    return result, False, "openai"
            except Exception as e:
                print(f"[RefundBuyerAgent] OpenAI call failed: {e}. Falling back.")

        return self.deterministic_extraction(raw_text), True, "deterministic_rule_engine"

    async def _call_gemini(self, raw_text: str) -> Optional[RefundRequestExtraction]:
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(
            f"{REFUND_SYSTEM_PROMPT}\nUser Request: {raw_text}"
        )
        return self._parse_json(response.text.strip())

    async def _call_groq(self, raw_text: str) -> Optional[RefundRequestExtraction]:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=self.groq_key)
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": REFUND_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        return self._parse_json(completion.choices[0].message.content)

    async def _call_openai(self, raw_text: str) -> Optional[RefundRequestExtraction]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.openai_key,
            base_url=settings.openai_base_url or None,
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": REFUND_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
        )
        return self._parse_json(response.choices[0].message.content)

    def _parse_json(self, text: str) -> Optional[RefundRequestExtraction]:
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text.strip())
        return RefundRequestExtraction(**data)

    def deterministic_extraction(self, raw_text: str) -> RefundRequestExtraction:
        """Deterministic regex-based refund request extraction."""
        t = raw_text.lower()

        # Extract order ID patterns
        order_id = None
        order_match = re.search(r'(?:order\s*(?:id|#|number)?[:\s]*)?([a-f0-9\-]{8,36})', t)
        if order_match:
            candidate = order_match.group(1)
            if len(candidate) >= 8:
                order_id = candidate

        # Categorize reason
        reason_category = "other"
        if any(k in t for k in ["damage", "damaged", "broken", "cracked", "dent"]):
            reason_category = "damaged"
        elif any(k in t for k in ["defect", "defective", "malfunction", "not working", "doesn't work", "faulty"]):
            reason_category = "defective"
        elif any(k in t for k in ["wrong item", "wrong product", "incorrect", "different product"]):
            reason_category = "wrong_item"
        elif any(k in t for k in ["not as described", "not as expected", "different from", "misleading"]):
            reason_category = "not_as_described"
        elif any(k in t for k in ["changed my mind", "don't want", "don't need", "no longer need", "changed mind"]):
            reason_category = "changed_mind"
        elif any(k in t for k in ["late", "delayed", "didn't arrive", "not delivered", "late delivery"]):
            reason_category = "late_delivery"

        # Extract reason text
        reason = raw_text.strip()
        if len(reason) > 500:
            reason = reason[:497] + "..."

        # Extract amount
        requested_amount = None
        amount_match = re.search(r'(?:₹|rs\.?|inr)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', t)
        if amount_match:
            requested_amount = float(amount_match.group(1).replace(',', ''))

        # Determine refund type
        refund_type = "full"
        if any(k in t for k in ["partial", "some", "part of"]):
            refund_type = "partial"
        elif requested_amount is not None:
            refund_type = "partial"

        return RefundRequestExtraction(
            order_id=order_id,
            reason=reason,
            reason_category=reason_category,
            requested_amount=requested_amount,
            refund_type=refund_type,
        )
