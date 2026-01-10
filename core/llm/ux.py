# core/llm/ux.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.artifacts.types import AgentEvent
from core.llm.client import LLMResponse


@dataclass(frozen=True)
class LLMUX:
    """
    LLM 결과를 사용자/이벤트/리포트 관점에서 표준화한 UX 모델.
    """
    ok: bool
    code: str  # ok | llm_disabled | network_unreachable | missing_api_key | llm_call_failed | unknown
    hint_line: str  # 리포트에 1줄로 들어갈 상태 문구
    event_type: str  # info | warning
    event_name: str  # executor.llm_used | executor.llm_fallback (등 고정)
    event_message: str  # 이벤트 메시지(짧고 일관된 표현)
    debug_details_md: str = ""  # last_error 등은 details로만(선택)


def build_llm_ux(llm_res: LLMResponse) -> LLMUX:
    """
    LLMResponse -> LLMUX 변환(전 Agent 공통)
    """
    if llm_res.ok:
        return LLMUX(
            ok=True,
            code="ok",
            hint_line="- LLM: 적용됨",
            event_type="info",
            event_name="executor.llm_used",
            event_message="[Executor] LLM 인사이트 생성 완료",
            debug_details_md="",
        )

    code = llm_res.error or "unknown"

    # 기본: 실패는 warning + fallback 이벤트로 통일
    event_type = "warning"
    event_name = "executor.llm_fallback"

    # 사용자에게 보여줄 상태 문구(리포트 1줄)
    if code == "llm_disabled":
        hint = "- LLM: 미적용 (LLM_ENABLED=false)"
    elif code == "network_unreachable":
        hint = "- LLM: 미적용 (외부 네트워크 불가/프록시 미설정)"
    elif code == "missing_api_key":
        hint = "- LLM: 미적용 (OPENROUTER_API_KEY 미설정)"
    elif code == "llm_call_failed":
        hint = "- LLM: 미적용 (호출 실패: primary/fallback 모두 실패)"
    else:
        hint = "- LLM: 미적용 (알 수 없는 오류)"

    # 이벤트 메시지(짧고 일관되게)
    # llm_res.content는 이미 “skip/설명” 문구로 내려오므로, 뒤에 code를 붙여 분류 가능하게만 유지
    msg = f"[Executor] {llm_res.content} ({code})"

    debug_md = ""
    if llm_res.last_error:
        debug_md = (
            "\n\n<details><summary>LLM debug</summary>\n\n"
            f"- error_code: {code}\n"
            f"- last_error: {llm_res.last_error}\n"
            "\n</details>\n"
        )

    return LLMUX(
        ok=False,
        code=code,
        hint_line=hint,
        event_type=event_type,
        event_name=event_name,
        event_message=msg,
        debug_details_md=debug_md,
    )


def build_llm_event(llm_ux: LLMUX) -> AgentEvent:
    """
    LLMUX -> AgentEvent 변환(전 Agent 공통)
    """
    return AgentEvent(
        type=llm_ux.event_type,
        name=llm_ux.event_name,
        message=llm_ux.event_message,
    )
