# apps/chainlit_app/app.py
from __future__ import annotations

from typing import Any, Dict, List

import chainlit as cl

from core.config.settings import get_settings
from core.agent.registry import AgentRegistry
from core.routing.router import Router
from core.agent.runner import AgentRunner

from apps.chainlit_app.ui.upload import handle_uploads  # 기존 업로드 처리 사용
from apps.chainlit_app.ui.render import render_result

# agents 등록 (예: dia)
from agents.dia.agent import DIAAgent
from agents.logcop.agent import LogCopAgent


def build_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(DIAAgent())
    # reg.register(LogCopAgent())  # 추후 추가
    return reg


@cl.on_chat_start
async def on_chat_start():
    settings = get_settings()

    registry = AgentRegistry()
    registry.register(DIAAgent())
    registry.register(LogCopAgent())

    # logcop 같은 추가 agent는 나중에 registry.register로 붙이면 됨
    # from agents.logcop.agent import LogCopAgent
    # registry.register(LogCopAgent())

    cl.user_session.set("settings", settings)
    cl.user_session.set("runner", AgentRunner(registry=registry, settings=settings))


def _normalize_uploaded_files(uploaded_files):
    norm = []
    for f in uploaded_files or []:
        if isinstance(f, dict):
            norm.append(f)
        else:
            # dataclass or object with attributes
            norm.append(
                {
                    "name": getattr(f, "name", None),
                    "path": getattr(f, "path", None),
                    "mime": getattr(f, "mime", None),
                }
            )
    # 필수값 없는 항목 제거
    return [x for x in norm if x.get("name") and x.get("path")]


@cl.on_message
async def on_message(message: cl.Message):
    settings = get_settings()

    # 1) 업로드 처리 (context 구성)
    uploaded_files = await handle_uploads(message, settings)
    print("[DBG] uploaded_files type:", type(uploaded_files), "first:", (uploaded_files[0] if uploaded_files else None))

    context = {
        "session_id": cl.user_session.get("id"),
        "uploaded_files": _normalize_uploaded_files(uploaded_files),
    }

    # 2) 자동 라우팅 → agent 선택
    runner: AgentRunner = cl.user_session.get("runner")


    # 3) 실행
    result = await runner.run(message.content, context=context)
    await render_result(result)
