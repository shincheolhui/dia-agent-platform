# core/context/normalize.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context.schema import AgentContext, UploadedFileRef


def _as_uploaded_file_ref(x: Any) -> Optional[UploadedFileRef]:
    """
    허용 입력:
    - UploadedFileRef
    - dict{name,path,mime}
    - dataclass/object with attributes name/path/mime (legacy)
    """
    if x is None:
        return None

    if isinstance(x, UploadedFileRef):
        return x

    if isinstance(x, dict):
        name = x.get("name")
        path = x.get("path")
        mime = x.get("mime")
        if name and path:
            return UploadedFileRef(name=str(name), path=str(path), mime=(str(mime) if mime else None))
        return None

    # legacy object/dc
    name = getattr(x, "name", None)
    path = getattr(x, "path", None)
    mime = getattr(x, "mime", None)
    if name and path:
        return UploadedFileRef(name=str(name), path=str(path), mime=(str(mime) if mime else None))
    return None


DEFAULT_SESSION_ID = "-"

def _coerce_str(v, default=DEFAULT_SESSION_ID) -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def normalize_context(raw: Optional[Dict[str, Any]]) -> AgentContext:
    """
    Runner/UI에서 전달되는 context(dict)를 AgentContext로 표준화.
    - 기존 형태(context["uploaded_files"]가 list[dict])를 그대로 지원
    - raw가 None이면 빈 컨텍스트 반환
    """
    raw = raw or {}
    session_id = _coerce_str(raw.get("session_id"))

    uploaded_files_raw: List[Any] = raw.get("uploaded_files") or []
    uploaded_files: List[UploadedFileRef] = []
    for f in uploaded_files_raw:
        ref = _as_uploaded_file_ref(f)
        if ref:
            uploaded_files.append(ref)

    meta = raw.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {"_raw_meta": meta}

    # raw에 meta 외 필드가 더 있으면 meta로 흡수 (호환/확장)
    extra = {k: v for k, v in raw.items() if k not in {"session_id", "uploaded_files", "meta"}}
    if extra:
        meta = dict(meta)
        meta.setdefault("_extra", {}).update(extra)

    return AgentContext(session_id=session_id, uploaded_files=uploaded_files, meta=meta)
