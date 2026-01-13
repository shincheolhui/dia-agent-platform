# core/agent/stages.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.artifacts.types import AgentEvent, ArtifactRef


# ----------------------------
# Stage DTOs
# ----------------------------
@dataclass
class StageContext:
    user_message: str
    context: Any
    settings: Any
    trace_id: str = "-"


@dataclass
class Plan:
    intent: str
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    ok: bool
    text: str
    artifacts: list[ArtifactRef] = field(default_factory=list)
    llm_used: bool = False
    file_kind: str = "unknown"
    error_code: Optional[str] = None

    # 디버그/관측 데이터(호환성 위해 명시적 필드로 둠)
    debug: dict[str, Any] = field(default_factory=dict)

    # 선택: 향후 확장(없어도 됨)
    llm_status: Optional[str] = None  # "ok"|"skipped"|"failed"
    llm_reason: Optional[str] = None  # "llm_disabled"|...
    llm_model: Optional[str] = None


@dataclass
class ReviewResult:
    approved: bool
    issues: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)


# ----------------------------
# Event builders (Chainlit UI / logs friendly)
# ----------------------------
def _ev(name: str, message: str, level: str = "info", data: Optional[dict[str, Any]] = None) -> AgentEvent:
    """
    AgentEvent는 프로젝트에서 dict 스타일로 쓰는 것을 전제로 함.
    (Chainlit UI에서 dict 이벤트 방어 로직도 반영되어 있음)
    """
    ev: dict[str, Any] = {
        "name": name,
        "message": message,
        "level": level,
    }
    if data is not None:
        ev["data"] = data
    return ev  # type: ignore[return-value]


def step_start(step: str, message: str) -> AgentEvent:
    return _ev(f"{step}.start", message, level="info")


def step_end(step: str, message: str) -> AgentEvent:
    return _ev(f"{step}.end", message, level="info")


def info(name: str, message: str) -> AgentEvent:
    return _ev(name, message, level="info")


def warn(name: str, message: str) -> AgentEvent:
    return _ev(name, message, level="warning")


def log(name: str, message: str) -> AgentEvent:
    # 일반 log 레벨(info)로 통일
    return _ev(name, message, level="info")


# ----------------------------
# Uploaded file helpers (dict / UploadedFileRef 모두 호환)
# ----------------------------
def _as_dict_like(obj: Any) -> Optional[dict[str, Any]]:
    return obj if isinstance(obj, dict) else None


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    """
    dict / 객체(UploadedFileRef 포함) 모두에서 안전하게 key를 가져온다.
    """
    d = _as_dict_like(obj)
    if d is not None:
        return d.get(key, default)
    return getattr(obj, key, default)


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _file_get(context_or_sc_context: Any) -> list[Any]:
    """
    context(dict or AgentContext-like)에서 uploaded_files를 list로 반환.
    """
    if context_or_sc_context is None:
        return []

    if isinstance(context_or_sc_context, dict):
        v = context_or_sc_context.get("uploaded_files") or []
        return v if isinstance(v, list) else []

    v = getattr(context_or_sc_context, "uploaded_files", None) or []
    return v if isinstance(v, list) else []


def _file_name_and_path(file_obj: Any) -> tuple[str, str, str, str]:
    """
    uploaded_files 원소(dict or UploadedFileRef)에서
    (name, path, ext, mime) 를 안전하게 추출한다.
    """
    path = _safe_str(_obj_get(file_obj, "path", ""), "")
    name = _safe_str(_obj_get(file_obj, "name", ""), "")
    mime = _safe_str(_obj_get(file_obj, "mime", ""), "")

    if not name and path:
        name = Path(path).name

    ext = Path(name or path).suffix.lower() if (name or path) else ""
    return name, path, ext, mime


# ----------------------------
# Meta Contract v1 (P2-2-C)
# ----------------------------
def build_agent_meta(
    *,
    agent_id: str,
    mode: str,
    file_kind: str,
    llm_used: bool,
    artifacts_count: int,
    approved: bool,
    error_code: Optional[str] = None,
    # 선택 입력(없어도 v1 기본값으로 정규화됨)
    llm_status: Optional[str] = None,   # "ok"|"skipped"|"failed"
    llm_reason: Optional[str] = None,   # "llm_disabled"|...
    llm_model: Optional[str] = None,    # "anthropic/..."|...
    review_issues: Optional[list[str]] = None,
    review_followups: Optional[list[str]] = None,
    trace_id: Optional[str] = None,
    # 기존 코드 호환: extra에 trace_id / review_issues 등을 넣던 패턴 흡수
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    P2-2-C Meta Contract v1.

    - 상위 필드는 항상 존재 (없으면 기본값)
    - 기존(legacy) 코드에서 extra로 넘기던 값(trace_id, review_issues 등)을 흡수
    - 기존 소비자 호환을 위해 legacy 필드(llm_used 등)를 top-level에도 유지
    """
    extra = extra or {}

    # extra에서 흡수(호환)
    if trace_id is None:
        trace_id = _safe_str(extra.get("trace_id"), "-") if isinstance(extra, dict) else "-"
    if review_issues is None:
        v = extra.get("review_issues") if isinstance(extra, dict) else None
        review_issues = v if isinstance(v, list) else []
    if review_followups is None:
        v = extra.get("review_followups") if isinstance(extra, dict) else None
        review_followups = v if isinstance(v, list) else []

    trace_id = _safe_str(trace_id, "-")
    review_issues = review_issues or []
    review_followups = review_followups or []

    # llm_status 기본값 결정
    if llm_status is None:
        llm_status = "ok" if llm_used else "skipped"

    # llm_reason 기본값: used=True면 None
    if llm_used:
        llm_reason = None

    meta_v1: dict[str, Any] = {
        "agent_id": str(agent_id),
        "mode": str(mode),
        "approved": bool(approved),
        "file_kind": str(file_kind or "unknown"),
        "artifacts_count": int(artifacts_count),
        "error_code": error_code,
        "llm": {
            "used": bool(llm_used),
            "status": str(llm_status),
            "reason": llm_reason,
            "model": llm_model,
        },
        "review": {
            "issues": list(review_issues),
            "followups": list(review_followups),
        },
        "trace_id": trace_id,
    }

    # legacy 호환 필드(기존 UI/로그/테스트가 참조할 가능성 대비)
    meta_v1["llm_used"] = bool(llm_used)
    meta_v1["approved_flag"] = bool(approved)

    # extra는 별도 공간에 보관(추후 디버깅/확장용)
    if extra:
        meta_v1["extra"] = dict(extra)

    return meta_v1
