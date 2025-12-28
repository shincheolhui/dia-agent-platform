from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.agent.base import AgentMeta
from core.agent.runner import AgentRunner
from agents.dia.graph import run_dia_graph


@dataclass
class DIAAgent:
    meta: AgentMeta = AgentMeta(
        agent_id="dia",
        name="DIA Agent",
        description="Planner–Executor–Reviewer loop for 업무 자동화 데모",
    )

    def build(self, settings: Any) -> AgentRunner:
        async def _run(user_message: str, context: Optional[Dict[str, Any]] = None):
            return await run_dia_graph(user_message=user_message, context=context or {}, settings=settings)

        return AgentRunner(run_fn=_run)


def get_agent() -> DIAAgent:
    return DIAAgent()
