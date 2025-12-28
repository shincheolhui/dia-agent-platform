from __future__ import annotations

from typing import Any, Dict

import chainlit as cl


async def run_dia_graph(user_message: str, context: Dict[str, Any], settings: Any):
    """
    MVP skeleton:
    - Show 3 steps (Planner/Executor/Reviewer) to prove 'Agent-ness'
    - Return a final response message
    """
    async with cl.Step(name="Planner Agent") as s1:
        plan = f"요청을 분석하고 작업을 3단계로 분해합니다.\n- 입력: {user_message}\n- 계획: 요약 → 실행 → 검증"
        s1.output = plan

    async with cl.Step(name="Executor Agent") as s2:
        result = f"현재는 MVP 단계이므로 실제 도구 실행 대신, 입력 내용을 정리했습니다.\n- 정리: {user_message}"
        s2.output = result

    async with cl.Step(name="Reviewer Agent") as s3:
        review = "결과가 요청 의도에 부합하는지 확인했습니다. (MVP) ✅ 승인"
        s3.output = review

    final_text = (
        "DIA Agent MVP 실행 완료입니다.\n\n"
        f"요청: {user_message}\n\n"
        "다음 단계에서 실제 Tool(파일 로드/분석/시각화/RAG)을 Executor에 연결하겠습니다."
    )
    return final_text
