# apps/chainlit_app/ui/render.py
from __future__ import annotations

from typing import List

import chainlit as cl

from core.artifacts.types import AgentResult, ArtifactRef, AgentEvent


async def render_events(events: List[AgentEvent]) -> None:
    """
    AgentEvent를 Chainlit Step으로 최소 렌더링
    - step_start/step_end를 기반으로 간단 그룹화
    - MVP에서는: 그냥 로그 형태로 보여도 충분
    """
    # MVP: 이벤트를 순서대로 출력 (과도한 복잡도 방지)
    for ev in events:
        if ev.type in ("step_start", "step_end"):
            # Step 형태로 보이게
            async with cl.Step(name=ev.name):
                if ev.message:
                    await cl.Message(content=ev.message).send()  # 반드시 await (메시지 누락/순서 꼬임 방지)
        else:
            # log
            if ev.message:
                await cl.Message(content=f"[{ev.name}] {ev.message}").send()


def _to_elements(artifacts: List[ArtifactRef]) -> List[cl.Element]:
    elements: List[cl.Element] = []
    for a in artifacts:
        if a.kind == "image":
            elements.append(cl.Image(name=a.name, path=a.path, display="inline"))
        else:
            elements.append(cl.File(name=a.name, path=a.path, display="inline"))
    return elements


async def render_result(result: AgentResult) -> None:
    # (선택) 이벤트 렌더
    if result.events:
        await render_events(result.events)

    elements = _to_elements(result.artifacts)
    await cl.Message(content=result.text, elements=elements).send()
