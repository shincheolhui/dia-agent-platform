# apps/chainlit_app/app.py
from __future__ import annotations

from typing import Any, Dict, List

import chainlit as cl

from core.config.settings import get_settings
from core.agent.registry import AgentRegistry
from core.routing.router import Router
from core.agent.runner import AgentRunner

from agents.dia.agent import DIAAgent
from apps.chainlit_app.ui.upload import handle_uploads  # 기존 업로드 처리 사용
from apps.chainlit_app.ui.render import render_result


def build_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(DIAAgent())
    # reg.register(LogCopAgent())  # 추후 추가
    return reg


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="DIA Agent Platform 준비 완료. 파일을 업로드하고 요청을 입력하세요.").send()


@cl.on_message
async def on_message(message: cl.Message):
    settings = get_settings()

    # 1) 업로드 처리 (context 구성)
    uploaded_files: List[Dict[str, Any]] = await handle_uploads(message, settings)
    context = {"uploaded_files": uploaded_files}

    # 2) 자동 라우팅 → agent 선택
    registry = build_registry()
    router = Router(registry)
    agent_id = router.pick_agent_id(user_message=message.content, context=context)
    agent = registry.get(agent_id)

    # 3) 실행
    runner = AgentRunner(agent=agent, settings=settings)
    result = await runner.run(message.content, context=context)

    # 4) UI 렌더
    await render_result(result)
