from __future__ import annotations

import chainlit as cl

from core.config.settings import get_settings
from core.agent.registry import load_agent
from apps.chainlit_app.ui.render import render_text
from apps.chainlit_app.ui.upload import handle_spontaneous_uploads


@cl.on_chat_start
async def on_chat_start():
    settings = get_settings()
    cl.user_session.set("settings", settings)

    agent = load_agent(settings.ACTIVE_AGENT)
    runner = agent.build(settings)

    cl.user_session.set("agent_meta", agent.meta)
    cl.user_session.set("runner", runner)
    cl.user_session.set("uploaded_files", [])

    await render_text(
        f"✅ {agent.meta.name} 준비 완료\n"
        f"- agent_id: {agent.meta.agent_id}\n"
        f"- description: {agent.meta.description}\n\n"
        "메시지에 파일(CSV/PDF)을 첨부하면 Executor가 실제 분석을 수행하고\n"
        "결과 아티팩트를 생성합니다."
    )


@cl.on_message
async def on_message(message: cl.Message):
    settings = cl.user_session.get("settings")
    runner = cl.user_session.get("runner")

    # 1) 사용자가 메시지에 첨부한 파일을 workspace/uploads로 복사 저장
    new_files = await handle_spontaneous_uploads(message, settings)
    if new_files:
        prev = cl.user_session.get("uploaded_files") or []
        prev.extend([f.__dict__ for f in new_files])
        cl.user_session.set("uploaded_files", prev)

    # 2) Agent 실행 시 context로 업로드 파일 목록 전달
    context = {"uploaded_files": cl.user_session.get("uploaded_files") or []}

    result = await runner.run(message.content, context=context)

    # 3) 결과 렌더링 (텍스트 + 파일 다운로드 element)
    if isinstance(result, dict) and "text" in result:
        await render_text(result["text"], elements=result.get("elements"))
    else:
        await render_text(str(result))
