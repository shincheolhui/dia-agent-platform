from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelPolicy:
    primary: str
    fallback: str


def get_model_policy(settings: Any) -> ModelPolicy:
    return ModelPolicy(
        primary=getattr(settings, "OPENROUTER_MODEL_PRIMARY", "anthropic/claude-3.5-sonnet"),
        fallback=getattr(settings, "OPENROUTER_MODEL_FALLBACK", "openai/gpt-4o-mini"),
    )