from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Workspace
    WORKSPACE_DIR: str = "workspace"
    
    ACTIVE_AGENT: str = "dia"

    # OpenRouter
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Model policy (string ids used by provider)
    PRIMARY_MODEL: str = "anthropic/claude-3.5-sonnet"
    FALLBACK_MODEL: str = "openai/gpt-4o-mini"

    # LLM options
    LLM_TIMEOUT_SEC: int = 45
    LLM_MAX_RETRIES: int = 1
    LLM_MAX_TOKENS: int = 900
    LLM_TEMPERATURE: float = 0.2
    LLM_ENABLED: bool = False  # 폐쇄망/데모 안정성: 기본 OFF 권장


    # OpenRouter Optional headers
    OPENROUTER_APP_TITLE: str = "dia-agent-platform"
    OPENROUTER_HTTP_REFERER: str = "http://localhost"


def get_settings() -> Settings:
    return Settings()
