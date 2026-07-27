"""
Application configuration.

All settings are loaded from environment variables (or a local `.env` file)
via pydantic-settings, so nothing sensitive is ever hard-coded. A single
`Settings` instance is created once and reused across the app.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = one directory above /app. Relative paths in .env are resolved
# against this so the service behaves the same regardless of CWD.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────
    app_name: str = "Developer Landing API"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000"]
    )

    # ── Storage / logging ──────────────────────────────────────────
    data_dir: str = "data"
    log_file: str = "data/logs/app.log"
    log_level: str = "INFO"

    # ── Rate limiting ──────────────────────────────────────────────
    rate_limit_max_requests: int = 5
    rate_limit_window_seconds: int = 60

    # ── AI provider ────────────────────────────────────────────────
    anthropic_api_key: str = ""
    ai_model: str = "claude-haiku-4-5"
    ai_timeout_seconds: float = 12.0
    ai_enabled: bool = True

    # ── Email / SMTP ───────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@example.com"
    smtp_from_name: str = "Developer Portfolio"
    owner_email: str = "owner@example.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Allow a comma-separated string in the env var."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ── Derived helpers ────────────────────────────────────────────
    @property
    def data_path(self) -> Path:
        return self._abs(self.data_dir)

    @property
    def log_path(self) -> Path:
        return self._abs(self.log_file)

    @property
    def ai_configured(self) -> bool:
        return self.ai_enabled and bool(self.anthropic_api_key)

    @property
    def email_configured(self) -> bool:
        """True when real SMTP delivery is possible; otherwise dry-run mode."""
        return bool(self.smtp_host and self.smtp_from_email)

    def _abs(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else BASE_DIR / p


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the file is parsed only once per process."""
    return Settings()
