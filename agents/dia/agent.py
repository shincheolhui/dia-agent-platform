# agents/dia/agent.py
from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent.base import BaseAgent
from core.artifacts.types import AgentResult
from agents.dia.graph import run_dia  # graph.py에서 chainlit 제거한 함수로 변경


class DIAAgent(BaseAgent):
    id = "dia"
    name = "DIA (Decision & Insight Automation)"
    description = "CSV/PDF 분석 및 보고서/그래프 생성 Agent"

    async def run(self, user_message: str, context: Optional[Dict[str, Any]], settings: Any) -> AgentResult:
        return await run_dia(user_message=user_message, context=context or {}, settings=settings)
