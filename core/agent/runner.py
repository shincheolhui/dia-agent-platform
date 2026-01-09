# core/agent/runner.py
from typing import Any, Dict, Optional

from core.agent.registry import AgentRegistry
from core.agent.router import decide_agent_id
from core.artifacts.types import AgentEvent, AgentResult
from core.context import normalize_context


class AgentRunner:
    def __init__(self, registry: AgentRegistry, settings: Any):
        self.registry = registry
        self.settings = settings

    async def run(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        # 0) context 표준화 (Phase2-1 핵심)
        ctx = normalize_context(context).to_dict()

        active = getattr(self.settings, "ACTIVE_AGENT", "dia")
        available = self.registry.list_ids()

        # 1) agent 선택 (라우팅)
        if active == "auto":
            decision = decide_agent_id(
                user_message=user_message,
                context=ctx,
                available_agent_ids=available,
                default_agent_id="dia",
            )
            agent_id = decision.agent_id
            route_event = AgentEvent(
                type="info",
                name="router",
                message=f"[router] agent={agent_id} (confidence={decision.confidence}) reason={decision.reason}",
            )
        else:
            agent_id = active
            route_event = AgentEvent(
                type="info",
                name="router",
                message=f"[router] ACTIVE_AGENT fixed to '{agent_id}'",
            )

        agent = self.registry.get(agent_id)
        if not agent:
            # fallback to dia if available
            fallback_id = "dia" if self.registry.has("dia") else (available[0] if available else None)
            if not fallback_id:
                return AgentResult(
                    text="실행 가능한 agent가 등록되어 있지 않습니다. agents 등록을 확인하세요.",
                    events=[
                        route_event,
                        AgentEvent(type="error", name="router", message="no agents registered"),
                    ],
                    artifacts=[],
                    meta={"ok": False, "error": "no_agents"},
                )
            agent = self.registry.get(fallback_id)
            agent_id = fallback_id
            route_event = AgentEvent(
                type="warning",
                name="router",
                message=f"[router] requested agent not found; fallback to '{agent_id}'",
            )

        # 2) agent 실행
        result = await agent.run(user_message=user_message, context=ctx, settings=self.settings)

        # 3) 라우팅 이벤트를 항상 맨 앞에 prepend
        result.events = [route_event] + (result.events or [])
        return result
