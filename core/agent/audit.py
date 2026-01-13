# core/agent/audit.py
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

try:
    # P2-2-A~C에서 stages helpers가 표준
    from core.agent.stages import _file_get, _file_name_and_path  # type: ignore
except Exception:  # pragma: no cover
    _file_get = None  # type: ignore
    _file_name_and_path = None  # type: ignore


def _bool_setting(settings: Any, key: str, default: bool) -> bool:
    v = getattr(settings, key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


def _int_setting(settings: Any, key: str, default: int) -> int:
    v = getattr(settings, key, default)
    try:
        return int(v)
    except Exception:
        return default


def _str_setting(settings: Any, key: str, default: str) -> str:
    v = getattr(settings, key, default)
    return default if v is None else str(v)


def _audit_dir(settings: Any) -> Path:
    # 우선순위: AUDIT_DIR > WORKSPACE_DIR/audit
    audit_dir = getattr(settings, "AUDIT_DIR", None)
    if audit_dir:
        return Path(str(audit_dir))
    workspace = getattr(settings, "WORKSPACE_DIR", "workspace")
    return Path(str(workspace)) / "audit"


def _json_default(o: Any):
    # dataclass → dict
    if is_dataclass(o):
        return asdict(o)

    # Path → str
    if isinstance(o, Path):
        return str(o)

    # bytes → len만
    if isinstance(o, (bytes, bytearray)):
        return {"_type": "bytes", "len": len(o)}

    # 그 외: string fallback
    return str(o)


def _safe_preview(text: str, max_len: int) -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def _normalize_artifacts(artifacts: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not artifacts:
        return out
    for a in artifacts:
        if isinstance(a, dict):
            out.append(
                {
                    "kind": a.get("kind"),
                    "name": a.get("name"),
                    "path": a.get("path"),
                    "mime_type": a.get("mime_type"),
                }
            )
        else:
            out.append(
                {
                    "kind": getattr(a, "kind", None),
                    "name": getattr(a, "name", None),
                    "path": getattr(a, "path", None),
                    "mime_type": getattr(a, "mime_type", None),
                }
            )
    return out


def _normalize_events_summary(events: Any, max_names: int = 30) -> Dict[str, Any]:
    if not events:
        return {"count": 0, "names": []}
    names: List[str] = []
    for ev in events:
        if isinstance(ev, dict):
            n = ev.get("name") or ev.get("type") or ""
        else:
            n = getattr(ev, "name", None) or getattr(ev, "type", None) or ""
        if n:
            names.append(str(n))
        if len(names) >= max_names:
            break
    return {"count": len(list(events)) if hasattr(events, "__len__") else len(names), "names": names}


def _normalize_files(context: Any, settings: Any) -> List[Dict[str, Any]]:
    """
    context(dict/AgentContext)에서 uploaded_files 메타만 추출.
    - path 저장은 정책에 따라 옵션 처리 가능
    """
    store_path = _bool_setting(settings, "AUDIT_STORE_FILE_PATH", True)

    files: List[Any] = []
    if _file_get is not None:
        try:
            files = _file_get(context)  # type: ignore
        except Exception:
            files = []
    else:
        # fallback
        if isinstance(context, dict):
            v = context.get("uploaded_files") or []
            files = v if isinstance(v, list) else []
        else:
            v = getattr(context, "uploaded_files", None) or []
            files = v if isinstance(v, list) else []

    out: List[Dict[str, Any]] = []
    for f in files[:10]:  # 상한(운영 안전)
        if _file_name_and_path is not None:
            try:
                name, path, ext, mime = _file_name_and_path(f)  # type: ignore
            except Exception:
                name, path, ext, mime = "", "", "", ""
        else:
            # fallback
            if isinstance(f, dict):
                name = str(f.get("name") or "")
                path = str(f.get("path") or "")
                mime = str(f.get("mime") or "")
            else:
                name = str(getattr(f, "name", "") or "")
                path = str(getattr(f, "path", "") or "")
                mime = str(getattr(f, "mime", "") or "")
            ext = Path(name or path).suffix.lower() if (name or path) else ""

        out.append(
            {
                "name": name,
                "path": (path if store_path else ""),
                "ext": ext,
                "mime": mime,
            }
        )
    return out


def build_audit_entry(
    *,
    result: Any,
    user_message: str,
    context: Any,
    settings: Any,
) -> Dict[str, Any]:
    """
    P2-2-D: Meta Contract v1을 포함한 감사용 엔트리 생성.
    - meta(v1)를 변형 없이 포함
    - 원문 메시지/파일경로 저장 여부는 settings로 제어
    """
    audit_enabled = _bool_setting(settings, "AUDIT_ENABLED", True)
    if not audit_enabled:
        return {"schema_version": "audit.v1", "disabled": True}

    store_message = _bool_setting(settings, "AUDIT_STORE_MESSAGE", False)
    max_len = _int_setting(settings, "AUDIT_MESSAGE_MAX_LEN", 200)

    meta = getattr(result, "meta", None)
    if meta is None and isinstance(result, dict):
        meta = result.get("meta")

    trace_id = "-"
    if isinstance(meta, dict) and meta.get("trace_id"):
        trace_id = str(meta.get("trace_id"))
    elif isinstance(context, dict) and context.get("session_id"):
        trace_id = str(context.get("session_id"))
    else:
        trace_id = str(getattr(context, "session_id", "-") or "-")

    artifacts = getattr(result, "artifacts", None)
    if artifacts is None and isinstance(result, dict):
        artifacts = result.get("artifacts")

    events = getattr(result, "events", None)
    if events is None and isinstance(result, dict):
        events = result.get("events")

    agent_id = None
    mode = None
    approved = None
    file_kind = None
    error_code = None

    if isinstance(meta, dict):
        agent_id = meta.get("agent_id")
        mode = meta.get("mode")
        approved = meta.get("approved")
        file_kind = meta.get("file_kind")
        error_code = meta.get("error_code")

    entry: Dict[str, Any] = {
        "schema_version": "audit.v1",
        "ts": ts(),
        "trace_id": trace_id,
        "agent": {
            "agent_id": agent_id,
            "mode": mode,
        },
        "outcome": {
            "approved": approved,
            "file_kind": file_kind,
            "error_code": error_code,
            "artifacts_count": len(artifacts or []),
        },
        "request": {
            "message_len": len(user_message or ""),
            "message_preview": _safe_preview(user_message or "", max_len),
        },
        "files": _normalize_files(context, settings),
        "artifacts": _normalize_artifacts(artifacts),
        "events_summary": _normalize_events_summary(events),
        "meta": meta,  # v1 contract 그대로 저장
    }

    if store_message:
        entry["request"]["message"] = user_message

    return entry


def export_audit_json(
    *,
    entry: Dict[str, Any],
    settings: Any,
) -> Path:
    """
    단건 JSON export 저장.
    """
    out_dir = ensure_dir(_audit_dir(settings))
    agent_id = ""
    trace_id = ""
    try:
        agent_id = str(((entry.get("agent") or {}).get("agent_id") or "")).strip()
    except Exception:
        agent_id = ""
    try:
        trace_id = str(entry.get("trace_id") or "").strip()
    except Exception:
        trace_id = ""

    fname = f"{ts()}__{safe_filename(agent_id or 'agent')}__{safe_filename(trace_id or '-')}.json"
    out_path = out_dir / fname
    out_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return out_path


def append_audit_jsonl(
    *,
    entry: Dict[str, Any],
    settings: Any,
) -> Path:
    """
    Append-only JSONL 저장.
    """
    out_dir = ensure_dir(_audit_dir(settings))
    out_path = out_dir / "audit.jsonl"
    line = json.dumps(entry, ensure_ascii=False, default=_json_default)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return out_path


def export_and_append(
    *,
    result: Any,
    user_message: str,
    context: Any,
    settings: Any,
) -> Tuple[Optional[Path], Optional[Path], Optional[Dict[str, Any]]]:
    """
    Runner에서 1회 호출용.
    - 실패해도 예외를 던지지 않고 (None, None, entry/None) 반환
    """
    try:
        entry = build_audit_entry(result=result, user_message=user_message, context=context, settings=settings)
    except Exception:
        return None, None, None

    # AUDIT_ENABLED=false면 파일 저장 안 함
    if entry.get("disabled") is True:
        return None, None, entry

    try:
        json_path = export_audit_json(entry=entry, settings=settings)
    except Exception:
        json_path = None

    try:
        jsonl_path = append_audit_jsonl(entry=entry, settings=settings)
    except Exception:
        jsonl_path = None

    return json_path, jsonl_path, entry
