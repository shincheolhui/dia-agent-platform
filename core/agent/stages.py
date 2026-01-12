# core/agent/stages.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.artifacts.types import AgentEvent, ArtifactRef


@dataclass
class StageContext:
    """
    모든 stage가 공유하는 런타임 컨텍스트.
    - user_message: 사용자의 입력 텍스트
    - context: normalize_context를 통과한 표준 컨텍스트(AgentContext 또는 dict 호환)
    - settings: 설정 객체
    - trace_id: 로깅/상관관계(trace_id/session_id)
    """
    user_message: str
    context: Any
    settings: Any
    trace_id: str = "-"


@dataclass
class Plan:
    """
    Planner 출력
    - intent: 높은 수준의 의도(예: "csv_analysis", "log_analysis")
    - assumptions/constraints: 실행 전 가정/제약
    - notes: 자유 메모(라우팅/파일/환경)
    """
    intent: str
    assumptions: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """
    Executor 출력
    - ok: 실행 성공/실패(실패라도 산출물을 만들 수 있음)
    - text: executor 단계 요약 메시지(AgentResult.text와는 별개)
    - artifacts: 생성 산출물
    - llm_used: LLM 사용 여부(성공 호출 기준)
    - file_kind: 입력 파일 종류(csv/pdf/text/log/unknown)
    - error_code: 실패/우회 상태코드 (llm_disabled, missing_api_key 등 포함 가능)
    - debug: 내부 디버그 메타
    """
    ok: bool
    text: str
    artifacts: List[ArtifactRef] = field(default_factory=list)
    llm_used: bool = False
    file_kind: str = "unknown"
    error_code: Optional[str] = None
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewResult:
    """
    Reviewer 출력
    - approved: 승인 여부
    - issues: 발견된 이슈(필수 섹션 누락, 산출물 없음 등)
    - followups: 사용자에게 요청할 추가 입력/조치
    """
    approved: bool
    issues: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)


# -----------------------------
# Event helpers (표준 네이밍)
# -----------------------------

def step_start(stage: str, message: str) -> AgentEvent:
    return AgentEvent(type="step_start", name=f"{stage}.start", message=message)


def step_end(stage: str, message: str) -> AgentEvent:
    return AgentEvent(type="step_end", name=f"{stage}.end", message=message)


def info(name: str, message: str) -> AgentEvent:
    return AgentEvent(type="info", name=name, message=message)


def log(name: str, message: str) -> AgentEvent:
    return AgentEvent(type="log", name=name, message=message)


def warn(name: str, message: str) -> AgentEvent:
    return AgentEvent(type="warning", name=name, message=message)


def error(name: str, message: str) -> AgentEvent:
    return AgentEvent(type="error", name=name, message=message)


def build_agent_meta(
    *,
    agent_id: str,
    mode: str,
    file_kind: str,
    llm_used: bool,
    artifacts_count: int,
    approved: bool,
    error_code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "agent_id": agent_id,
        "mode": mode,
        "file_kind": file_kind,
        "llm_used": llm_used,
        "artifacts_count": artifacts_count,
        "approved": approved,
    }
    if error_code:
        meta["error_code"] = error_code
    if extra:
        meta.update(extra)
    return meta


def _file_get(f: Any, key: str, default: Any = None) -> Any:
    """
    UploadedFileRef(속성) / dict(get) / 기타 객체(getattr) 모두 지원
    """
    if f is None:
        return default
    if isinstance(f, dict):
        return f.get(key, default)
    # UploadedFileRef/dataclass류: name/path/mime 같은 필드 접근
    if hasattr(f, key):
        return getattr(f, key) or default
    return default

def _file_name_and_path(f: Any) -> Tuple[str, str]:
    name = str(_file_get(f, "name", "") or "")
    path = str(_file_get(f, "path", "") or "")
    if not name and path:
        name = Path(path).name
    return name, path