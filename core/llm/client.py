from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.llm.models import get_model_policy

try:
    # langchain-openai
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None


@dataclass
class LLMResponse:
    ok: bool
    content: str
    error: Optional[str] = None


class LLMClient:
    """
    OpenRouter 기반 LLM 클라이언트.
    - Key가 없으면 실행은 되되, 'LLM 미사용' 메시지를 반환(해커톤 안정성)
    - Key가 있으면 primary -> fallback 순으로 호출
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self.policy = get_model_policy(settings)

    def _has_key(self) -> bool:
        key = getattr(self.settings, "OPENROUTER_API_KEY", None)
        return bool(key and str(key).strip())

    def _headers(self) -> Dict[str, str]:
        # OpenRouter 권장 헤더(옵션)
        return {
            "HTTP-Referer": getattr(self.settings, "OPENROUTER_HTTP_REFERER", "http://localhost"),
            "X-Title": getattr(self.settings, "OPENROUTER_APP_TITLE", "dia-agent-platform"),
        }

    def _build_llm(self, model: str):
        if ChatOpenAI is None:
            raise RuntimeError("langchain_openai is not installed")

        return ChatOpenAI(
            model=model,
            api_key=getattr(self.settings, "OPENROUTER_API_KEY", None),
            base_url=getattr(self.settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers=self._headers(),
            temperature=float(getattr(self.settings, "LLM_TEMPERATURE", 0.2)),
            max_tokens=int(getattr(self.settings, "LLM_MAX_TOKENS", 900)),
            timeout=int(getattr(self.settings, "LLM_TIMEOUT_SEC", 45)),
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        # 1) Key 없으면 즉시 폴백
        if not self._has_key():
            return LLMResponse(
                ok=False,
                content=(
                    "LLM API Key가 설정되지 않아 인사이트 생성(LLM 호출)을 건너뜁니다.\n"
                    "OPENROUTER_API_KEY를 .env에 설정하면 요약/인사이트/액션을 자동 생성합니다."
                ),
                error="missing_api_key",
            )

        # 2) Key 있으면 Primary → 실패 시 Fallback
        last_err: str | None = None
        models_to_try = [self.policy.primary, self.policy.fallback]

        max_retries = int(getattr(self.settings, "LLM_MAX_RETRIES", 1))
        attempts = 0

        for model in models_to_try:
            # 각 모델당 (1 + max_retries) 번 시도
            for _ in range(1 + max_retries):
                attempts += 1
                try:
                    llm = self._build_llm(model)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]
                    resp = await llm.ainvoke(messages)
                    text = getattr(resp, "content", "") or ""
                    if text.strip():
                        return LLMResponse(ok=True, content=text)
                    last_err = f"empty_response(model={model})"
                except Exception as e:  # 네트워크/429/모델 오류 등
                    last_err = f"{type(e).__name__}: {e}"

        return LLMResponse(
            ok=False,
            content=f"LLM 호출에 실패했습니다. (primary/fallback 모두 실패)\n- last_error: {last_err}",
            error="llm_call_failed",
        )