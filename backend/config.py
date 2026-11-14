"""Application configuration loader."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """App settings loaded from environment variables."""

    # AI Provider API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # AI Provider Priority Order (default: free providers only)
    # Add anthropic/openai to the list if you have paid API keys
    AI_PROVIDER_PRIORITY: list[str] = os.getenv(
        "AI_PROVIDER_PRIORITY", "gemini,groq"
    ).split(",")

    # App Config
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Phase 3: Alerts
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    ALERT_SCAN_INTERVAL_HOURS: int = int(os.getenv("ALERT_SCAN_INTERVAL_HOURS", "4"))

    # Timeouts
    AI_CALL_TIMEOUT: int = int(os.getenv("AI_CALL_TIMEOUT", "60"))  # seconds per AI call
    AI_JUDGE_TIMEOUT: int = int(os.getenv("AI_JUDGE_TIMEOUT", "90"))  # judge gets extra time (larger prompt)
    AI_RETRY_ON_TIMEOUT: bool = os.getenv("AI_RETRY_ON_TIMEOUT", "true").lower() in ("true", "1", "yes")

    # Stock Data Source
    # "google_finance" (default) — scrapes Google Finance, works behind corporate proxies
    # "yfinance"                 — uses yfinance library (may hang behind Zscaler)
    # "auto"                     — tries Google Finance first, falls back to yfinance
    STOCK_DATA_SOURCE: str = os.getenv("STOCK_DATA_SOURCE", "google_finance")


settings = Settings()
