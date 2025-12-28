from __future__ import annotations

import chainlit as cl


class StepTracer:
    """
    Minimal tracer to show Planner/Executor/Reviewer steps in Chainlit.
    This is intentionally simple for hackathon stability.
    """

    async def step(self, name: str, content: str) -> None:
        async with cl.Step(name=name) as s:
            s.output = content
