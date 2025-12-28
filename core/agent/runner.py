from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class AgentRunner:
    """
    A thin wrapper that standardizes how the UI calls agents.
    """

    def __init__(self, run_fn: Callable[[str, Optional[Dict[str, Any]]], Any]):
        self._run_fn = run_fn

    async def run(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Any:
        return await self._run_fn(user_message, context)
