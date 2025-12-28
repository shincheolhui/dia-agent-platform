from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.config.settings import Settings
from core.llm.models import ModelPolicy

# LangChain
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


@dataclass
class LLMResult:
    ok: bool
    content: str
    model: str
    error: Optional[str] = None


class LLMClient:
    """
    OpenRouter 기반 LLM 클라이언트.
    - Key가 없으면 실행은 되되, 'LLM 미사용' 메시지를 반환(해커톤 안정성)
    - Key가 있으면 primary -> fallback 순으로 호출
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.policy = ModelPolicy(
            primary=settings.PRIMARY_MODEL,
            fallback=settings.FALLBACK_MODEL,
        )

    def _mk_client(self, model: str) -> ChatOpenAI:
        # OpenRouter는 OpenAI 호환 엔드포인트 패턴 사용
        # base_url + api_key만 맞추면 됨
        return ChatOpenAI(
            model=model,
            api_key=self.settings.OPENROUTER_API_KEY,
            base_url=self.settings.OPENROUTER_BASE_URL,
            temperature=self.settings.LLM_TEMPERATURE,
            timeout=self.settings.LLM_TIMEOUT_SEC,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        # Key 없으면 "안전 폴백" (개발/데모가 멈추지 않게)
        if not (self.settings.OPENROUTER_API_KEY or "").strip():
            return LLMResult(
                ok=False,
                content=(
                    "LLM API Key가 설정되지 않아 인사이트 생성(LLM 호출)을 건너뜁니다.\n"
                    "OPENROUTER_API_KEY를 .env에 설정하면 요약/인사이트/액션을 자동 생성합니다."
                ),
                model="none",
                error="missing_api_key",
            )

        last_err: Optional[str] = None

        for model in self.policy.all():
            try:
                llm = self._mk_client(model)
                msgs = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
                resp = await llm.ainvoke(msgs)
                text = (getattr(resp, "content", "") or "").strip()
                return LLMResult(ok=True, content=text, model=model)
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"

        return LLMResult(ok=False, content="LLM 호출에 실패했습니다.", model=self.policy.fallback, error=last_err)
