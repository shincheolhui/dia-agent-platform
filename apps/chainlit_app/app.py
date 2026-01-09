# apps/chainlit_app/app.py
from __future__ import annotations

import sys
import logging
import chainlit as cl

from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (core, agents import 안정화)
ROOT_DIR = Path(__file__).resolve().parents[2]  # dia-agent-platform/
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from typing import Any, Dict, List

from core.config.settings import get_settings
from core.agent.registry import AgentRegistry
from core.agent.runner import AgentRunner
from core.logging.logger import setup_logging, get_logger

from apps.chainlit_app.ui.upload import handle_uploads  # 기존 업로드 처리 사용
from apps.chainlit_app.ui.render import render_result

# agents 등록 (예: dia)
from agents.dia.agent import DIAAgent
from agents.logcop.agent import LogCopAgent


log = get_logger(__name__)
_trace_filter = None


def build_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(DIAAgent())
    reg.register(LogCopAgent())
    return reg


@cl.on_chat_start
async def on_chat_start():
    global _trace_filter
    settings = get_settings()
    registry = build_registry()

    cl.user_session.set("settings", settings)
    cl.user_session.set("runner", AgentRunner(registry=registry, settings=settings))

    if _trace_filter is None:
        _trace_filter = setup_logging(
            workspace_dir=getattr(settings, "WORKSPACE_DIR", "workspace"),
            level=logging.INFO,
        )
    log.info(f"chainlit chat started with settings: {settings}")


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
    global _trace_filter
    settings = get_settings()
    session_id = cl.user_session.get("id")

    if _trace_filter:
        _trace_filter.set_trace_id(session_id)

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
