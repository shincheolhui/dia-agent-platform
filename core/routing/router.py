# core/routing/router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.agent.registry import AgentRegistry
from core.routing.rules import route_rules


class Router:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def pick_agent_id(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        context = context or {}
        uploaded_files: List[Dict[str, str]] = context.get("uploaded_files", [])
        agent_id = route_rules(user_message, uploaded_files)

        # 안전장치: registry에 없으면 기본 dia
        if not self.registry.has(agent_id):
            return "dia"
        return agent_id
