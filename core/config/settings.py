from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ACTIVE_AGENT: str = "dia"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Model policy (string ids used by provider)
    PRIMARY_MODEL: str = "anthropic/claude-3.5-sonnet"
    FALLBACK_MODEL: str = "openai/gpt-4o-mini"
    LLM_TEMPERATURE: float = Field(default=0.2)
    LLM_TIMEOUT_SEC: int = Field(default=60)

    # Workspace
    WORKSPACE_DIR: str = "workspace"


def get_settings() -> Settings:
    return Settings()
