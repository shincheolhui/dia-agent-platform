from __future__ import annotations

import chainlit as cl

from core.config.settings import get_settings
from core.agent.registry import load_agent
from apps.chainlit_app.ui.render import render_text


@cl.on_chat_start
async def on_chat_start():
    settings = get_settings()
    cl.user_session.set("settings", settings)

    agent = load_agent(settings.ACTIVE_AGENT)
    runner = agent.build(settings)

    cl.user_session.set("agent_meta", agent.meta)
    cl.user_session.set("runner", runner)

    await render_text(
        f"✅ {agent.meta.name} 준비 완료\n"
        f"- agent_id: {agent.meta.agent_id}\n"
        f"- description: {agent.meta.description}\n\n"
        "메시지를 입력하면 Planner/Executor/Reviewer Step이 표시됩니다."
    )


@cl.on_message
async def on_message(message: cl.Message):
    runner = cl.user_session.get("runner")
    result = await runner.run(message.content, context={})
    await render_text(str(result))
