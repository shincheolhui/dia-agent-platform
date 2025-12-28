from __future__ import annotations

from typing import List, Optional

import chainlit as cl


async def render_text(content: str, elements: Optional[List[cl.Element]] = None) -> None:
    await cl.Message(content=content, elements=elements or []).send()
