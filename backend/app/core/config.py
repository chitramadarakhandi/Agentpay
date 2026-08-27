"""AgentPay backend configuration."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "AgentPay"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # Database
    database_url: str = "sqlite+aiosqlite:///./agentpay.db"

    # LLM
    llm_provider: Literal["gemini", "groq", "openai", "none"] = "none"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""

    # Razorpay (TEST MODE ONLY)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Demo
    demo_mode: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "none":
            return False
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "groq":
            return bool(self.groq_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
