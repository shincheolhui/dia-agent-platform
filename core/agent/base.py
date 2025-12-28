from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentMeta:
    agent_id: str
    name: str
    description: str


class BaseAgent(Protocol):
    meta: AgentMeta

    def build(self, settings: Any) -> Any:
        """Return an executable agent runner (callable/graph/etc.)."""
        ...
