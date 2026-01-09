# apps/chainlit_app/app.py
from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Any, Dict, List

import chainlit as cl

# 프로젝트 루트를 sys.path에 추가 (core, agents import 안정화)
ROOT_DIR = Path(__file__).resolve().parents[2]  # dia-agent-platform/
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config.settings import get_settings
from core.agent.registry import AgentRegistry
from core.agent.runner import AgentRunner
from core.logging.logger import setup_logging, get_logger, set_trace_id

from apps.chainlit_app.ui.upload import handle_uploads
from apps.chainlit_app.ui.render import render_result

from agents.dia.agent import DIAAgent
from agents.logcop.agent import LogCopAgent


log = get_logger(__name__)
_logging_initialized = False


def build_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(DIAAgent())
    reg.register(LogCopAgent())
    return reg


def _normalize_uploaded_files(uploaded_files: Any) -> List[Dict[str, Any]]:
    """
    Chainlit 업로드 결과가 dict 또는 객체/데이터클래스 형태일 수 있으므로
    name/path/mime 필드만 표준 dict로 정규화한다.
    """
    norm: List[Dict[str, Any]] = []
    for f in uploaded_files or []:
        if isinstance(f, dict):
            norm.append(
                {
                    "name": f.get("name"),
                    "path": f.get("path"),
                    "mime": f.get("mime"),
                }
            )
        else:
            norm.append(
                {
                    "name": getattr(f, "name", None),
                    "path": getattr(f, "path", None),
                    "mime": getattr(f, "mime", None),
                }
            )
    return [x for x in norm if x.get("name") and x.get("path")]


def _mask_settings(settings: Any) -> Dict[str, Any]:
    """
    settings 객체를 로그에 남길 때 민감정보를 마스킹한다.
    (Pydantic Settings / dataclass / 일반 객체를 폭넓게 지원)
    """
    if hasattr(settings, "model_dump"):
        data = settings.model_dump()
    elif hasattr(settings, "dict"):
        data = settings.dict()
    else:
        data = dict(getattr(settings, "__dict__", {}))

    for k in list(data.keys()):
        lk = str(k).lower()
        if "api_key" in lk or "token" in lk or "secret" in lk or "password" in lk:
            v = data.get(k)
            if v:
                s = str(v)
                data[k] = (s[:6] + "..." if len(s) > 6 else "***")
            else:
                data[k] = None
    return data


@cl.on_chat_start
async def on_chat_start():
    global _logging_initialized

    settings = get_settings()
    registry = build_registry()
    runner = AgentRunner(registry=registry, settings=settings)

    cl.user_session.set("settings", settings)
    cl.user_session.set("runner", runner)

    # ✅ 로깅은 프로세스 전체에서 1회만 초기화
    # ✅ 옵션 A: enable_console=False (콘솔은 Chainlit 기본 출력만 사용)
    if not _logging_initialized:
        setup_logging(
            workspace_dir=getattr(settings, "WORKSPACE_DIR", "workspace"),
            level=logging.INFO,
            enable_console=False,  # ✅ 핵심: 중복 콘솔 출력 방지
        )
        _logging_initialized = True

    # trace_id: 세션 id(없으면 "-")
    session_id = cl.user_session.get("id") or "-"
    set_trace_id(str(session_id))

    log.info("chainlit chat started (settings masked): %s", _mask_settings(settings))


@cl.on_message
async def on_message(message: cl.Message):
    # 세션에 저장된 settings/runner를 재사용
    settings = cl.user_session.get("settings") or get_settings()
    runner: AgentRunner = cl.user_session.get("runner")

    if runner is None:
        registry = build_registry()
        runner = AgentRunner(registry=registry, settings=settings)
        cl.user_session.set("runner", runner)

    # trace_id 갱신 (세션 단위)
    session_id = cl.user_session.get("id") or "-"
    set_trace_id(str(session_id))

    # 1) 업로드 처리
    uploaded_files_raw = await handle_uploads(message, settings)
    uploaded_files = _normalize_uploaded_files(uploaded_files_raw)

    if uploaded_files:
        log.info(
            "uploaded_files detected: count=%d first_name=%s first_path=%s",
            len(uploaded_files),
            uploaded_files[0].get("name"),
            uploaded_files[0].get("path"),
        )
    else:
        log.info("uploaded_files detected: count=0")

    context = {
        "session_id": str(session_id),
        "uploaded_files": uploaded_files,
    }

    # 2) 실행
    result = await runner.run(message.content, context=context)

    # 3) 렌더
    await render_result(result)
