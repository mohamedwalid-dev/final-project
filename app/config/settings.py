"""
⚙️ Application Settings
Centralized configuration loader using Pydantic Settings (v2).
Reads all config from a single .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Enterprise Operating System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── LLM / AI ──────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "google"          # google | openai | ollama
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── LangChain / Generation ───────────────────────────────────────────────
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024

    # ── MongoDB ──────────────────────────────────────────────────────────────
    MONGO_BACKEND: str = "atlas"          # atlas | local
    MONGO_URI: str
    MONGO_DB: str

    # TLS / Atlas options
    MONGO_TLS_DISABLE_OCSP: bool = False
    MONGO_TLS_INSECURE: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Scan / Scheduler Intervals ───────────────────────────────────────────
    LEAVE_SCAN_INTERVAL_SEC: int = 300
    TICKET_SCAN_INTERVAL_SEC: int = 120
    LEAD_SCAN_INTERVAL_SEC: int = 600
    EVENT_SCAN_INTERVAL_SEC: int = 60
    DB_WATCHER_INTERVAL_SEC: int = 30

    # ── Webhooks / Security ──────────────────────────────────────────────────
    WEBHOOK_SECRET: str = ""

    # ── Pydantic v2 Config ───────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",   # ❗ يمنع أي config غير معروف
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached singleton.
    Use this everywhere instead of calling Settings() directly.
    """
    return Settings()