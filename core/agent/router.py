# core/agent/router.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class RouteDecision:
    agent_id: str
    confidence: float
    reason: str


LOG_EXTS = {".log", ".txt", ".out"}
DATA_EXTS = {".csv", ".xlsx", ".xls", ".pdf"}

LOG_KEYWORDS = {
    "error", "exception", "stacktrace", "traceback", "caused by",
    "timeout", "pkix", "ssl", "connection",
    "에러", "오류", "예외", "원인", "장애", "실패",
}


def _ctx_uploaded_files(context: Any) -> List[Dict[str, Any]]:
    """
    context가 AgentContext(표준) 또는 dict(레거시)여도
    uploaded_files를 list[dict{name,path,mime}] 형태로 뽑아준다.
    """
    if context is None:
        return []

    # 1) dict legacy
    if isinstance(context, dict):
        files = context.get("uploaded_files") or []
        out: List[Dict[str, Any]] = []
        for f in files:
            if isinstance(f, dict):
                name = f.get("name")
                path = f.get("path")
                mime = f.get("mime")
            else:
                name = getattr(f, "name", None)
                path = getattr(f, "path", None)
                mime = getattr(f, "mime", None)
            if name and path:
                out.append({"name": str(name), "path": str(path), "mime": (str(mime) if mime else None)})
        return out

    # 2) AgentContext 표준(duck typing)
    files = getattr(context, "uploaded_files", None) or []
    out2: List[Dict[str, Any]] = []
    for f in files:
        if isinstance(f, dict):
            name = f.get("name")
            path = f.get("path")
            mime = f.get("mime")
        else:
            name = getattr(f, "name", None)
            path = getattr(f, "path", None)
            mime = getattr(f, "mime", None)
        if name and path:
            out2.append({"name": str(name), "path": str(path), "mime": (str(mime) if mime else None)})
    return out2


def decide_agent_id(
    *,
    user_message: str,
    context: Any,
    available_agent_ids: Sequence[str],
    default_agent_id: str = "dia",
) -> RouteDecision:
    """
    라우팅 규칙:
    1) 파일 확장자 기반 (우선순위 최상)
    2) 키워드 기반
    3) fallback
    """
    available = list(available_agent_ids or [])
    if not available:
        return RouteDecision(agent_id=default_agent_id, confidence=0.1, reason="no available agents; default")

    uploaded_files = _ctx_uploaded_files(context)
    msg = (user_message or "").lower()

    # 1) 파일 확장자 기반
    if uploaded_files:
        f0 = uploaded_files[0]
        ext = Path(str(f0.get("path", ""))).suffix.lower()

        if ext in LOG_EXTS and "logcop" in available:
            return RouteDecision(agent_id="logcop", confidence=0.95, reason=f"file_ext={ext} -> logcop")

        if ext in DATA_EXTS and "dia" in available:
            # csv/xlsx/pdf 등은 DIA 우선
            return RouteDecision(agent_id="dia", confidence=0.90, reason=f"file_ext={ext} -> dia")

    # 2) 키워드 기반
    if any(k in msg for k in LOG_KEYWORDS) and "logcop" in available:
        return RouteDecision(agent_id="logcop", confidence=0.80, reason="keyword_match -> logcop")

    # 3) fallback
    if default_agent_id in available:
        return RouteDecision(agent_id=default_agent_id, confidence=0.60, reason="fallback default_agent_id")
    return RouteDecision(agent_id=available[0], confidence=0.55, reason="fallback first_available")
