# core/agent/runner.py
from __future__ import annotations

from typing import Any, Dict, Optional

from core.artifacts.types import AgentResult, AgentEvent
from core.agent.base import BaseAgent


class AgentRunner:
    def __init__(self, agent: BaseAgent, settings: Any):
        self.agent = agent
        self.settings = settings

    async def run(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        context = context or {}
        try:
            res = await self.agent.run(user_message=user_message, context=context, settings=self.settings)
            return res
        except Exception as e:
            # UI 독립 에러 포맷 (어댑터가 동일하게 처리)
            return AgentResult(
                text="처리 중 오류가 발생했습니다. (데모 안정 종료)",
                artifacts=[],
                events=[
                    AgentEvent(type="log", name="exception", level="error", message=str(e)),
                ],
                meta={"error": "exception"},
            )
