# core/routing/rules.py
from __future__ import annotations

from typing import Dict, List


def route_rules(user_message: str, uploaded_files: List[Dict[str, str]]) -> str:
    """
    최소 자동 라우팅 규칙 (Phase 1):
    - 현재는 dia 1개만 안정적으로 라우팅
    - 추후 logcop, etc. 추가 시 여기만 확장
    """
    # 예: 특정 키워드면 logcop으로 보내는 확장 포인트
    text = (user_message or "").lower()

    # if "log" in text or "에러" in text or "stacktrace" in text:
    #     return "logcop"

    return "dia"
