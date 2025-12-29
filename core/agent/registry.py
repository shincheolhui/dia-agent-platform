# core/agent/registry.py
from __future__ import annotations

from typing import Dict

from core.agent.base import BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents
