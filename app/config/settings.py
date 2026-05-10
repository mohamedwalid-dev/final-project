"""
⚙️ Application Settings
يقرأ كل config من ملف .env واحد — Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Enterprise Operating System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── LLM ──────────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "google"                    # google | openai | ollama
    GOOGLE_API_KEY: str = ""                        # Gemini API key
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── LangChain ────────────────────────────────────────────────────────────
    LLM_TEMPERATURE: float = 0.1                    # low = more deterministic
    LLM_MAX_TOKENS: int = 1024

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Scan Intervals ───────────────────────────────────────────────────────
    LEAVE_SCAN_INTERVAL_SEC: int = 300
    TICKET_SCAN_INTERVAL_SEC: int = 120
    LEAD_SCAN_INTERVAL_SEC: int = 600
    EVENT_SCAN_INTERVAL_SEC: int = 60
    DB_WATCHER_INTERVAL_SEC: int = 30

    # ── Webhook ───────────────────────────────────────────────────────────────
    WEBHOOK_SECRET: str = ""

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — call this everywhere instead of Settings()."""
    return Settings()