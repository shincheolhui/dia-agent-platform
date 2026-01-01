from __future__ import annotations

from typing import Any, Dict

from core.agent.base import BaseAgent
from core.artifacts.types import AgentResult
from agents.logcop.graph import run_logcop


class LogCopAgent(BaseAgent):
    id = "logcop"
    name = "LogCop"
    description = "로그/에러 텍스트를 요약하고 이슈/액션을 정리합니다."

    async def run(self, user_message: str, context: Dict[str, Any], settings: Any) -> AgentResult:
        return await run_logcop(user_message=user_message, context=context, settings=settings)
