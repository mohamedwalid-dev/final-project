"""
⚙️ Application Settings
Centralized configuration loader using Pydantic Settings (v2).
Reads all config from a single .env file.

v3 — Node.js API migration:
    ✅ كل متغيرات MONGO_* اتشالت — التطبيق مبقاش بيتصل بـ MongoDB مباشرة
       (Motor/pymongo)؛ كل الوصول للداتا بيعدي عبر Node.js Express API
       (انظر core/node_api_client.py + core/node_finance_proxy.py +
       core/node_hr_proxy.py).
    ✅ أُضيف قسم NODE_API_* — نفس المتغيرات اللي node_api_client.py
       كان بيقراها مباشرة بـ os.getenv()، دلوقتي موحّدة هنا في Settings
       عشان تبقى مصدر واحد للحقيقة، وعشان تتفعّل معاها validation
       بتاعة Pydantic (بدل fallback صامت لقيم افتراضية).

v3.1 — Self-renewing Node auth:
    ✅ أُضيف NODE_API_SERVICE_EMAIL / NODE_API_SERVICE_PASSWORD صراحةً
       هنا (كانوا بيتقروا بس بـ os.getenv() جوه node_api_client.py من
       غير ما يكونوا معرّفين في Settings — مع extra="forbid" ده مكنش
       بيوقع بس كان معناه إنهم مش موثّقين/متحققين هنا).
    ✅ أُضيف NODE_API_TOKEN_REFRESH_MARGIN_SEC — المدة قبل انتهاء
       التوكن الحالي اللي NodeAPIClient بيجدده فيها تلقائيًا (login()
       تاني) قبل ما يوصل لحظة الانتهاء الفعلية ويرجّع 401.

⚠️ IMPORTANT: لو عندك أسطر MONGO_* لسه موجودة في ملف .env بتاعك،
   لازم تمسحها أو تحطها في تعليق (#) — extra="forbid" هيرفض يشغّل
   التطبيق لو لقى أي متغير مش معرّف هنا في الكلاس.
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

    # ── Node.js API (system of record — replaces direct MongoDB access) ───────
    # الـ base URL بتاع الـ Node.js/Express API. الافتراضي بيفترض إن
    # Node شغال محلياً على بورت 5005 تحت /v1.
    NODE_API_BASE_URL: str = "http://localhost:5005/v1"

    # ✅ الطريقة الموصى بيها: بيانات حساب يقدر NodeAPIClient يعمله login
    # لوحده وقت الإقلاع، وبعدين يجدد الـ JWT تلقائيًا قبل ما ينتهي
    # (Node's Verify middleware عمره ~20 دقيقة في الكودبيز ده) —
    # بيحل مشكلة الـ 401 المتكرر نهائيًا بدل توكن ثابت بيموت بسرعة.
    NODE_API_SERVICE_EMAIL: str = ""
    NODE_API_SERVICE_PASSWORD: str = ""

    # JWT/service-account token ثابت — fallback قديم/لاختبار قصير المدى
    # بس. فاضي = هتاخد 401 على كل الـ endpoints المحمية لو مفيش
    # email/password. لو محطوط، بينتهي مع انتهاء صلاحيته الأصلية ومفيش
    # تجديد تلقائي له (استخدم email/password بدل منه في production).
    NODE_API_SERVICE_TOKEN: str = ""

    # Per-call timeout (ثواني)
    NODE_API_TIMEOUT_SEC: float = 10.0

    # عدد المحاولات لو حصل timeout/network error/5xx (مش بيعيد المحاولة لـ 4xx)
    NODE_API_MAX_RETRIES: int = 2

    # الأساس اللي بيتضاعف عليه الانتظار بين المحاولات (exponential backoff)
    NODE_API_RETRY_BACKOFF_BASE_SEC: float = 0.4

    # مدة صلاحية الكاش الداخلي (in-memory) لنتائج GET المتكررة
    NODE_API_CACHE_TTL_SEC: float = 20.0

    # Circuit breaker — بعد كام فشل متتالي يفتح الدايرة ويوقف المحاولات مؤقتاً
    NODE_API_CB_FAILURE_THRESHOLD: int = 5
    NODE_API_CB_COOLDOWN_SEC: float = 30.0

    # قد ايه (بالثواني) قبل انتهاء صلاحية التوكن الحالي (exp claim) نعمل
    # proactive re-auth تلقائي — بدل ما نستنى نرجع 401 ونعمل reactive retry.
    NODE_API_TOKEN_REFRESH_MARGIN_SEC: float = 120.0

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    FINANCE_DASHBOARD_CACHE_TTL_SEC: int = 300

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Scan / Scheduler Intervals ───────────────────────────────────────────
    LEAVE_SCAN_INTERVAL_SEC: int = 300
    TICKET_SCAN_INTERVAL_SEC: int = 120
    LEAD_SCAN_INTERVAL_SEC: int = 600
    EVENT_SCAN_INTERVAL_SEC: int = 60
    DB_WATCHER_INTERVAL_SEC: int = 30
    DASHBOARD_KPI_INTERVAL_SEC: int = 60

    # ── Webhooks / Security ──────────────────────────────────────────────────
    WEBHOOK_SECRET: str = ""

    # ── Agentic Layer Security ───────────────────────────────────────────────
    # API key checked against the X-Agentic-API-Key request header on every
    # /agentic/* endpoint. Empty ("") = auth DISABLED (open). Set a non-empty
    # value in .env to require the header. The agentic layer makes sensitive
    # HR/Finance decisions, so production deployments SHOULD set this.
    AGENTIC_API_KEY: str = ""

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