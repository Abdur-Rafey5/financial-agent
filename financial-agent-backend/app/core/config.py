"""
Application configuration.

All settings are loaded from environment variables with sensible defaults
for local development. Production deployments MUST override secrets via
environment variables or a secrets manager.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────────
    APP_NAME: str = "AI Financial Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./financial_agent.db",
        description="Async database URL",
    )
    DATABASE_URL_SYNC: str = Field(
        default="sqlite:///./financial_agent.db",
        description="Sync database URL for migrations",
    )

    # ── JWT Authentication ───────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-this-to-a-long-random-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Google Gemini ────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 30.0

    # ── Alpha Vantage ────────────────────────────────────────────────
    ALPHA_VANTAGE_API_KEY: str = ""
    MARKET_DATA_CACHE_TTL_SECONDS: int = 900  # 15 minutes
    # When no Alpha Vantage key is set, optionally fall back to Yahoo
    # Finance's public quote endpoints (no key required). Default off so
    # tests stay hermetic; enable in development or self-hosted deployments.
    MARKET_KEYLESS_FALLBACK: bool = False

    # ── Seeding ──────────────────────────────────────────────────────
    SEED_DEFAULT_CATEGORIES: bool = True
    SEED_DEMO_DATA: bool = False

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # ── Server ───────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Singleton settings instance
settings = Settings()
