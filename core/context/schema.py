# core/context/schema.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class UploadedFileRef:
    """
    UI/Runner/Agent 어디에서도 Chainlit 타입을 몰라도 되도록 표준 파일 참조.
    """
    name: str
    path: str
    mime: Optional[str] = None


@dataclass
class AgentContext:
    """
    Agent 실행 컨텍스트 표준.
    - Phase2-1에서 '고정'할 최소 필드만 둔다.
    - 확장 필드는 meta에 넣는다.
    """
    session_id: Optional[str] = None
    uploaded_files: List[UploadedFileRef] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "uploaded_files": [
                {"name": f.name, "path": f.path, "mime": f.mime} for f in self.uploaded_files
            ],
            "meta": dict(self.meta or {}),
        }
