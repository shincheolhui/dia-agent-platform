# core/agent/registry.py
from __future__ import annotations

from typing import Dict, List

from agents.dia.agent import DIAAgent
from agents.logcop.agent import LogCopAgent
from core.agent.base import BaseAgent


class AgentRegistry:
    """
    Agent 등록/조회 레지스트리.
    - UI/Runner는 여기만 의존한다.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def list_ids(self) -> List[str]:
        return sorted(self._agents.keys())


def build_default_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(DIAAgent())
    reg.register(LogCopAgent())
    return reg