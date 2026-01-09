# core/llm/client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.llm.models import get_model_policy
from core.logging.logger import get_logger

log = get_logger(__name__)

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None


@dataclass
class LLMResponse:
    ok: bool
    content: str
    # error: missing_api_key | llm_call_failed | llm_disabled | network_unreachable
    error: Optional[str] = None
    last_error: Optional[str] = None


class LLMClient:
    """
    OpenRouter 기반 LLM 클라이언트.
    - LLM_ENABLED=false면 아예 호출하지 않음(폐쇄망/데모 안정성)
    - Key가 없으면 실행은 되되, 'LLM 미사용' 메시지 반환
    - Key가 있으면 primary -> fallback 순으로 호출
    - 네트워크 불가(APIConnectionError 등)는 UX에서 "환경 제약"으로 분류
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self.policy = get_model_policy(settings)

    def _enabled(self) -> bool:
        return bool(getattr(self.settings, "LLM_ENABLED", True))

    def _has_key(self) -> bool:
        key = getattr(self.settings, "OPENROUTER_API_KEY", None)
        return bool(key and str(key).strip())

    def _headers(self) -> Dict[str, str]:
        return {
            "HTTP-Referer": getattr(self.settings, "OPENROUTER_HTTP_REFERER", "http://localhost"),
            "X-Title": getattr(self.settings, "OPENROUTER_APP_TITLE", "dia-agent-platform"),
        }

    def _is_network_error(self, e: Exception) -> bool:
        name = type(e).__name__
        msg = str(e).lower()

        network_names = {
            "APIConnectionError",
            "ConnectError",
            "ConnectionError",
            "ConnectTimeout",
            "ReadTimeout",
            "TimeoutException",
            "NewConnectionError",
            "NameResolutionError",
        }
        if name in network_names:
            return True

        network_markers = [
            "connection error",
            "failed to establish a new connection",
            "name or service not known",
            "nodename nor servname provided",
            "temporary failure in name resolution",
            "dns",
            "connect timeout",
            "read timeout",
            "timed out",
            "proxy error",
            "tunnel connection failed",
        ]
        return any(m in msg for m in network_markers)

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
            max_retries=0,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        # 0) 사용자가/환경이 LLM 비활성화
        if not self._enabled():
            log.info("llm.skip reason=llm_disabled")
            return LLMResponse(
                ok=False,
                content="현재 환경 설정(LLM_ENABLED=false)으로 LLM 인사이트 생성을 건너뜁니다.",
                error="llm_disabled",
            )

        # 1) Key 없으면 즉시 폴백
        if not self._has_key():
            log.info("llm.skip reason=missing_api_key")
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

        for model in models_to_try:
            for attempt in range(1, 2 + max_retries):
                try:
                    llm = self._build_llm(model)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]
                    resp = await llm.ainvoke(messages)
                    text = getattr(resp, "content", "") or ""
                    if text.strip():
                        log.info("llm.ok model=%s attempt=%s chars=%s", model, attempt, len(text))
                        return LLMResponse(ok=True, content=text)

                    last_err = f"empty_response(model={model})"
                    log.warning("llm.empty model=%s attempt=%s", model, attempt)

                except Exception as e:
                    if self._is_network_error(e):
                        log.warning("llm.skip reason=network_unreachable model=%s err=%s", model, f"{type(e).__name__}: {e}")
                        return LLMResponse(
                            ok=False,
                            content="외부 네트워크 연결이 불가하여(폐쇄망/차단/프록시 미설정) LLM 인사이트 생성을 건너뜁니다.",
                            error="network_unreachable",
                            last_error=f"{type(e).__name__}: {e}",
                        )

                    last_err = f"{type(e).__name__}: {e}"
                    log.warning("llm.fail model=%s attempt=%s err=%s", model, attempt, last_err)

        log.error("llm.giveup err=%s", last_err)
        return LLMResponse(
            ok=False,
            content="LLM 호출에 실패했습니다. (primary/fallback 모두 실패)",
            error="llm_call_failed",
            last_error=last_err,
        )
