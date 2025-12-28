from __future__ import annotations

from importlib import import_module
from typing import Dict

from core.agent.base import BaseAgent


def load_agent(agent_id: str) -> BaseAgent:
    """
    Load an agent plugin by id.
    Convention: agents/<agent_id>/agent.py exposes `get_agent()`.
    """
    module_path = f"agents.{agent_id}.agent"
    mod = import_module(module_path)
    if not hasattr(mod, "get_agent"):
        raise RuntimeError(f"{module_path} must expose get_agent()")
    return mod.get_agent()


def list_agents() -> Dict[str, str]:
    """
    Minimal registry for now. We can make it dynamic later.
    """
    return {
        "dia": "Decision & Insight Automation Agent",
    }
