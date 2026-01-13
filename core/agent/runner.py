# core/agent/runner.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.agent.audit import export_and_append
from core.agent.stages import log as evlog, warn
from core.artifacts.types import AgentResult
from core.context import normalize_context


@dataclass
class RouteDecision:
    agent_id: str
    confidence: float
    reason: str


class AgentRunner:
    """
    기존 앱(apps/chainlit_app/app.py)과 호환되는 시그니처 유지:
      AgentRunner(registry=..., settings=...)

    - registry는 agent_id -> agent_instance(or factory) 를 제공한다고 가정
    - agent는 .run(user_message, context, settings) async 메서드를 제공
    """

    def __init__(self, *, registry: Any, settings: Any):
        self.registry = registry
        self.settings = settings

    def route(self, ctx: Any) -> RouteDecision:
        """
        기존 정책(확장자 기반) 그대로:
        - .log -> logcop
        - .csv/.pdf -> dia
        - default -> dia
        """
        uploaded = []
        if isinstance(ctx, dict):
            uploaded = ctx.get("uploaded_files") or []
        else:
            uploaded = getattr(ctx, "uploaded_files", None) or []

        ext = ""
        if uploaded:
            f0 = uploaded[0]
            path = ""
            if isinstance(f0, dict):
                path = str(f0.get("path") or "")
            else:
                path = str(getattr(f0, "path", "") or "")
            ext = Path(path).suffix.lower()

        if ext == ".log":
            return RouteDecision(agent_id="logcop", confidence=0.95, reason="file_ext=.log -> logcop")
        if ext in (".csv", ".pdf"):
            return RouteDecision(agent_id="dia", confidence=0.9, reason=f"file_ext={ext} -> dia")
        return RouteDecision(agent_id="dia", confidence=0.6, reason="default -> dia")

    def _get_agent(self, agent_id: str) -> Any:
        """
        registry 구현 다양성 방어:
        - dict registry: registry[agent_id]
        - object registry: registry.get(agent_id) 또는 registry.resolve(agent_id) 등
        - callable(factory)인 경우 호출하여 instance 생성
        """
        agent = None

        if isinstance(self.registry, dict):
            agent = self.registry.get(agent_id)
        else:
            # 흔한 패턴들 순서대로 시도
            if hasattr(self.registry, "get"):
                try:
                    agent = self.registry.get(agent_id)
                except Exception:
                    agent = None
            if agent is None and hasattr(self.registry, "resolve"):
                try:
                    agent = self.registry.resolve(agent_id)
                except Exception:
                    agent = None

        if agent is None:
            raise KeyError(f"agent not found in registry: {agent_id}")

        # factory면 생성
        if callable(agent) and not hasattr(agent, "run"):
            agent = agent()

        return agent

    async def run(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        실행 흐름:
        - context normalize
        - route
        - agent.run
        - (P2-2-D) audit export/jsonl append (best-effort)
        """
        ctx = normalize_context(context)

        decision = self.route(ctx)
        agent = self._get_agent(decision.agent_id)

        # agent 실행
        result: AgentResult = await agent.run(user_message=user_message, context=ctx, settings=self.settings)

        # -------------------------
        # P2-2-D: audit export (best-effort)
        # -------------------------
        try:
            json_path, jsonl_path, entry = export_and_append(
                result=result,
                user_message=user_message,
                context=ctx,
                settings=self.settings,
            )

            # 이벤트로 남김(Chainlit UI에서 확인 가능)
            if json_path or jsonl_path:
                msg = "audit saved"
                if json_path:
                    msg += f" json={json_path.name}"
                if jsonl_path:
                    msg += f" jsonl={jsonl_path.name}"
                result.events.append(evlog("audit.saved", msg))
            else:
                if entry and entry.get("disabled") is True:
                    result.events.append(evlog("audit.disabled", "AUDIT_ENABLED=false"))

        except Exception as e:
            # audit 실패는 전체 실행을 깨지 않음
            result.events.append(warn("audit.failed", f"audit export failed: {type(e).__name__}: {e}"))

        return result
