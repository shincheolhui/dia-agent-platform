from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RouteDecision:
    agent_id: str
    reason: str
    confidence: float = 0.7

LOG_EXTS = {".log", ".txt", ".out"}

LOG_KEYWORDS = {
    # 영문
    "error", "exception", "stacktrace", "traceback", "caused by", "timeout",
    # 한글
    "에러", "오류", "예외", "원인", "장애", "실패",
}

def _contains_log_keyword(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in LOG_KEYWORDS)


def _ext(path: str) -> str:
    return Path(path).suffix.lower()


def decide_agent_id(
    user_message: str,
    context: Dict[str, Any],
    available_agent_ids: List[str],
    default_agent_id: str = "dia",
) -> RouteDecision:
    """
    Rule-based auto routing (LLM 없이도 동작하도록).
    - available_agent_ids에 존재하는 agent만 반환한다.
    - 없으면 default_agent_id로 fallback.
    """
    msg = (user_message or "").lower()

    uploaded_files: List[Dict[str, Any]] = context.get("uploaded_files", []) or []
    file_exts = []
    for f in uploaded_files:
        p = f.get("path") or ""
        if p:
            file_exts.append(_ext(p))

    # 0) 파일 기반 라우팅: LOG/TXT/OUT → LOGCOP
    if any(e in LOG_EXTS for e in file_exts):
        if "logcop" in available_agent_ids:
            return RouteDecision(
                agent_id="logcop",
                reason=f"uploaded_files ext={sorted(set(file_exts))} → logcop",
                confidence=0.95,
            )

    # 1) 파일 기반 라우팅: CSV/PDF → DIA
    if any(e in [".csv", ".xlsx", ".xls", ".pdf"] for e in file_exts):
        if "dia" in available_agent_ids:
            return RouteDecision(agent_id="dia", reason=f"uploaded_files ext={sorted(set(file_exts))} → dia", confidence=0.9)

    # 2) 로그 분석 계열 키워드 → logcop (있으면)
    if _contains_log_keyword(user_message or ""):
        if "logcop" in available_agent_ids:
            return RouteDecision(
                agent_id="logcop",
                reason="message contains log/error keywords → logcop",
                confidence=0.8,
            )

    # 3) 기본 fallback
    if default_agent_id in available_agent_ids:
        return RouteDecision(agent_id=default_agent_id, reason=f"fallback → {default_agent_id}", confidence=0.6)

    # 4) 최후 fallback: available 중 첫 번째
    if available_agent_ids:
        return RouteDecision(agent_id=available_agent_ids[0], reason="fallback → first available agent", confidence=0.5)

    # 5) 이 경우는 구조적으로 문제(agents 등록 자체가 안 된 상태)
    return RouteDecision(agent_id="dia", reason="no agents registered; fallback hardcoded to dia", confidence=0.1)
