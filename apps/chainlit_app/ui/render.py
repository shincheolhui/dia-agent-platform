from __future__ import annotations

import chainlit as cl


async def render_text(content: str) -> None:
    await cl.Message(content=content).send()
