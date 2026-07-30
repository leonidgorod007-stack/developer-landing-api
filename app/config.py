from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Developer Landing API"
    app_env: str = "development"
    debug: bool = True
    reload: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8000"]
    )

    data_dir: str = "data"
    log_file: str = "data/logs/app.log"
    log_level: str = "INFO"

    rate_limit_max_requests: int = 5
    rate_limit_window_seconds: int = 60

    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    # How outbound AI calls handle proxies:
    #   ""            -> direct connection, ignore system proxy env (works with VPN/proxy on)
    #   "system"/"env"-> use the OS/system proxy settings
    #   "http://host:port" -> use this proxy explicitly
    anthropic_proxy: str = ""
    ai_model: str = "claude-sonnet-5"
    ai_timeout_seconds: float = 12.0
    ai_enabled: bool = True

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
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
        return bool(self.smtp_host and self.smtp_from_email)

    def _abs(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else BASE_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
