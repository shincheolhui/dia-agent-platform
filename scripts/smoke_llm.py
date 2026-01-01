from __future__ import annotations

import asyncio

from core.config.settings import get_settings
from core.llm.client import LLMClient


async def main():
    settings = get_settings()
    client = LLMClient(settings)

    system_prompt = "You are a helpful analyst. Return concise output."
    user_prompt = "Say 'LLM OK' and summarize what you are doing in one sentence."

    res = await client.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    print("ok:", res.ok)
    print("error:", res.error)
    print("content:\n", res.content)


if __name__ == "__main__":
    asyncio.run(main())
