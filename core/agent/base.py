# core/agent/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.artifacts.types import AgentResult


class BaseAgent(ABC):
    id: str
    name: str
    description: str

    @abstractmethod
    async def run(self, user_message: str, context: Optional[Dict[str, Any]], settings: Any) -> AgentResult:
        raise NotImplementedError
