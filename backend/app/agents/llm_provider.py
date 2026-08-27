"""LLM Provider abstraction supporting Gemini, Groq, OpenAI, and Deterministic Fallback.

Never crashes if API key is missing or service is down.
Always falls back to deterministic rule-based extraction.
"""

import json
import re
from typing import Optional
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.buyer import StructuredRequirements

settings = get_settings()


SYSTEM_PROMPT = """You are an AI Buyer Agent requirement parser for AgentPay.
Extract structured product requirements from the user's natural language request.
Return strictly valid JSON matching this schema:
{
  "category": "laptops" | "phones" | "accessories",
  "budget_max": number | null,
  "budget_min": number | null,
  "minimum_ram_gb": number | null,
  "minimum_storage_gb": number | null,
  "maximum_delivery_days": number | null,
  "purpose": string | null,
  "preferred_brands": string[] | null,
  "required_features": string[] | null,
  "preferred_os": string | null
}
Do NOT include markdown backticks or commentary, only raw JSON.
"""


class LLMProvider:
    """Multi-provider LLM interface with robust error handling and fallback."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.gemini_key = settings.gemini_api_key
        self.groq_key = settings.groq_api_key
        self.openai_key = settings.openai_api_key

    async def extract_requirements(self, raw_text: str) -> tuple[StructuredRequirements, bool, str]:
        """Extract structured requirements from natural text.
        
        Returns:
            (StructuredRequirements, used_fallback: bool, provider_name: str)
        """
        if self.provider == "gemini" and self.gemini_key:
            try:
                result = await self._call_gemini(raw_text)
                if result:
                    return result, False, "gemini"
            except Exception as e:
                print(f"[LLM] Gemini call failed: {e}. Falling back to deterministic.")

        elif self.provider == "groq" and self.groq_key:
            try:
                result = await self._call_groq(raw_text)
                if result:
                    return result, False, "groq"
            except Exception as e:
                print(f"[LLM] Groq call failed: {e}. Falling back to deterministic.")

        elif self.provider == "openai" and self.openai_key:
            try:
                result = await self._call_openai(raw_text)
                if result:
                    return result, False, "openai"
            except Exception as e:
                print(f"[LLM] OpenAI call failed: {e}. Falling back to deterministic.")

        # Fallback to deterministic regex & keyword parser
        return self.deterministic_fallback_extraction(raw_text), True, "deterministic_rule_engine"

    async def _call_gemini(self, raw_text: str) -> Optional[StructuredRequirements]:
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(
            f"{SYSTEM_PROMPT}\nUser Request: {raw_text}"
        )
        text = response.text.strip()
        return self._parse_json_response(text)

    async def _call_groq(self, raw_text: str) -> Optional[StructuredRequirements]:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=self.groq_key)
        chat_completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        return self._parse_json_response(content)

    async def _call_openai(self, raw_text: str) -> Optional[StructuredRequirements]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.openai_key,
            base_url=settings.openai_base_url or None
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return self._parse_json_response(content)

    def _parse_json_response(self, text: str) -> Optional[StructuredRequirements]:
        # Strip code blocks if present
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text.strip())
        return StructuredRequirements(**data)

    def deterministic_fallback_extraction(self, text: str) -> StructuredRequirements:
        """Deterministic regex and NLP heuristic parser with Multilingual (EN, KN, HI) support."""
        t = text.lower()

        # Category
        category = "laptops"
        if any(k in t for k in ["phone", "mobile", "smartphone", "ಫೋನ್", "ಮೊಬೈಲ್", "फ़ोन", "मोबाइल"]):
            category = "phones"
        elif any(k in t for k in ["keyboard", "mouse", "monitor", "hub", "accessory", "accessories", "ಕೀಬೋರ್ಡ್", "ಕೀಬೋರ್ಡ್", "ಮಾઉસ", "माउस", "कीबोर्ड"]):
            category = "accessories"
        elif any(k in t for k in ["laptop", "macbook", "notebook", "workstation", "pc", "computer", "ಲ್ಯಾಪ್ಟಾಪ್", "ಲ್ಯಾಪ್‌ಟಾಪ್", "ಕಂಪ್ಯೂಟರ್", "लैपटॉप", "कंप्यूटर"]):
            category = "laptops"

        # Budget
        budget_max = None
        # Match patterns like: under 80000, under 80k, 70000 रुपये के अंदर, 70000 ರೂಪಾಯಿ ಒಳಗೆ
        budget_patterns = [
            r'(?:under|below|max|budget of|less than|<|up to|within|olage|ಒಳಗೆ|ಅಡಿಯಲ್ಲಿ|andar|अंदर|नीचे|कम|बजट|ಬಜೆಟ್)\s*(?:rs\.?|₹|ರೂ|रुपये|रुपए)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*(k|lakh|l|हज़ार|हजार|ಸಾವಿರ|ಲಕ್ಷ)?',
            r'(?:rs\.?|₹|ರೂ|रुपये|रुपए)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*(k|lakh|l|हज़ार|हजार|ಸಾವಿರ|ಲಕ್ಷ)?\s*(?:max|budget|olage|ಒಳಗೆ|andar|अंदर)?',
            r'([0-9]{4,7})\s*(?:rs\.?|₹|ರೂ|रुपये|रुपए|olage|ಒಳಗೆ|andar|अंदर|budget|ಬಜೆಟ್|बजट)?',
        ]
        for pat in budget_patterns:
            m = re.search(pat, t)
            if m:
                val_str = m.group(1).replace(',', '')
                val = float(val_str)
                unit = (m.group(2) if len(m.groups()) >= 2 and m.group(2) else "").lower()
                if unit in ('k', 'हज़ार', 'हजार', 'ಸಾವಿರ'):
                    val *= 1000
                elif unit in ('lakh', 'l', 'लाख', 'ಲಕ್ಷ'):
                    val *= 100000
                budget_max = val
                break

        # RAM
        ram_gb = None
        ram_match = re.search(r'([0-9]+)\s*(?:gb|gig|g)\s*(?:of\s+)?ram', t)
        if not ram_match:
            ram_match = re.search(r'ram\s*(?:>=|:|at least|min)?\s*([0-9]+)\s*(?:gb)?', t)
        if ram_match:
            ram_gb = int(ram_match.group(1))

        # Storage
        storage_gb = None
        storage_match = re.search(r'([0-9]+)\s*(?:gb|tb)\s*(?:ssd|hdd|storage|nvme)', t)
        if not storage_match:
            storage_match = re.search(r'storage\s*(?:>=|:|at least|min)?\s*([0-9]+)\s*(?:gb|tb)?', t)
        if storage_match:
            val = int(storage_match.group(1))
            if "tb" in t[max(0, storage_match.start()-5):min(len(t), storage_match.end()+5)]:
                val *= 1024
            storage_gb = val

        # Delivery days
        delivery_days = None
        delivery_match = re.search(r'(?:within|in|delivery in|delivery within)\s*([0-9]+)\s*(?:day|days)', t)
        if delivery_match:
            delivery_days = int(delivery_match.group(1))

        # Purpose
        purpose = None
        if "ai" in t or "ml" in t or "machine learning" in t or "deep learning" in t:
            purpose = "AI/ML development"
        elif "gaming" in t or "game" in t:
            purpose = "Gaming"
        elif "coding" in t or "programming" in t or "software" in t:
            purpose = "Software Development"
        elif "design" in t or "video" in t:
            purpose = "Content Creation"

        return StructuredRequirements(
            category=category,
            budget_max=budget_max,
            budget_min=None,
            minimum_ram_gb=ram_gb,
            minimum_storage_gb=storage_gb,
            maximum_delivery_days=delivery_days,
            purpose=purpose,
            preferred_brands=None,
            required_features=None,
            preferred_os="Windows" if "windows" in t else ("macOS" if "mac" in t else None)
        )
