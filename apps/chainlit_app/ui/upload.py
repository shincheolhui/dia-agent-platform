# apps/chainlit_app/ui/upload.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import chainlit as cl

from core.config.settings import Settings
from core.utils.fs import copy_to, safe_filename
from core.utils.time import ts


@dataclass
class UploadedFile:
    name: str
    path: str
    mime: str | None = None


def _get_workspace_upload_dir(settings: Settings) -> Path:
    return Path(settings.WORKSPACE_DIR) / "uploads"


async def handle_spontaneous_uploads(message: cl.Message, settings: Settings) -> List[UploadedFile]:
    """
    사용자가 메시지에 첨부한 파일(드래그/클립)을 받아서 workspace/uploads 로 복사 저장.
    Chainlit 문서: on_message에서 message.elements로 접근 가능. :contentReference[oaicite:0]{index=0}
    """
    uploaded: List[UploadedFile] = []

    if not getattr(message, "elements", None):
        return uploaded

    for el in message.elements:
        # Chainlit File element는 .path를 제공한다 (업로드된 임시 경로).
        src = getattr(el, "path", None)
        name = getattr(el, "name", None)
        mime = getattr(el, "mime", None)

        if not src or not name:
            continue

        safe_name = safe_filename(name)
        dst_name = f"{ts()}__{safe_name}"
        dst_path = copy_to(src, _get_workspace_upload_dir(settings), dst_name)

        uploaded.append(UploadedFile(name=safe_name, path=str(dst_path), mime=mime))

    return uploaded


async def handle_uploads(message: cl.Message, settings: Settings):
    """
    app.py에서 호출하는 표준 업로드 진입점
    - 내부적으로 handle_spontaneous_uploads를 사용
    - 반환 타입은 Agent/Core가 소비 가능한 dict 구조
    """
    files = await handle_spontaneous_uploads(message, settings)

    # Agent/Core가 Chainlit/Dataclass를 몰라도 되도록 dict로 변환
    return [
        {
            "name": f.name,
            "path": f.path,
            "mime": f.mime,
        }
        for f in files
    ]
