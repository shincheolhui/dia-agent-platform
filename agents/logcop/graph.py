# agents/logcop/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agent.reviewer import ReviewSpec, review_execution
from core.agent.stages import (
    StageContext,
    Plan,
    ExecutionResult,
    ReviewResult,
    step_start,
    step_end,
    info,
    log as evlog,
    warn,
    build_agent_meta,
    _file_name_and_path,
)
from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt
from core.tools.file_loader import load_file


def _artifact_dir(settings: Any) -> Path:
    return Path(getattr(settings, "WORKSPACE_DIR", "workspace")) / "artifacts"


def _save_markdown(settings: Any, title: str, body: str) -> Path:
    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.md"
    out_path = out_dir / filename
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _get_data(load_res: Any) -> dict:
    data = getattr(load_res, "data", None)
    return data if isinstance(data, dict) else {}


def _rule_based_log_insights(text: str) -> str:
    lowered = (text or "").lower()
    hits = []
    for k in ["exception", "error", "stacktrace", "traceback", "caused by", "timeout", "pkix", "ssl", "connection"]:
        if k in lowered:
            hits.append(k)

    lines: List[str] = []
    lines.append("## 요약")
    lines.append("- 업로드된 로그/텍스트에서 오류 징후를 스캔했습니다.")
    if hits:
        lines.append(f"- 탐지 키워드: {', '.join(hits)}")
    else:
        lines.append("- 명확한 오류 키워드는 탐지되지 않았습니다.")

    lines.append("\n## 권장 액션")
    lines.append("- 에러 발생 시각/요청 단위로 주변 로그(전후 200~500라인)를 확보하세요.")
    lines.append("- `Exception / Caused by` 체인 최하단(root cause) 메시지를 우선 확인하세요.")
    lines.append("- 네트워크/SSL 이슈라면 프록시/사내 인증서/CRL 정책을 먼저 점검하세요.")

    lines.append("\n## 주의사항")
    lines.append("- 본 결과는 규칙 기반이며, 시스템/서비스 맥락(구성/버전/배포)을 추가로 확인해야 합니다.")
    return "\n".join(lines)


def _get_uploaded_files(context: Any) -> List[Dict[str, Any]]:
    """
    context가 AgentContext(속성) 또는 dict 형태일 수 있으므로 안전하게 추출
    """
    if isinstance(context, dict):
        v = context.get("uploaded_files", []) or []
        return v if isinstance(v, list) else []
    v = getattr(context, "uploaded_files", None) or []
    return v if isinstance(v, list) else []


def _normalize_llm_meta(llm_res: Any, settings: Any) -> tuple[bool, str, Optional[str], Optional[str]]:
    ok = bool(getattr(llm_res, "ok", False))
    err = getattr(llm_res, "error", None)
    model = getattr(llm_res, "model", None) or getattr(settings, "PRIMARY_MODEL", None)

    if ok:
        return True, "ok", None, model
    if err in ("llm_disabled", "missing_api_key"):
        return False, "skipped", err, model
    return False, "failed", (err or "llm_call_failed"), model


def _plan(sc: StageContext) -> tuple[Plan, List[AgentEvent]]:
    events: List[AgentEvent] = []
    events.append(step_start("planner", "요청 해석 및 작업 분해 시작"))

    uploaded_files = _get_uploaded_files(sc.context)
    has_file = bool(uploaded_files)

    plan = Plan(
        intent="log_analysis",
        assumptions=[
            "입력은 로그(.log) 또는 텍스트(.txt/.out)일 수 있음",
            "LLM은 환경/설정에 따라 비활성 또는 실패할 수 있음",
        ],
        constraints=[
            "파일 로딩은 load_file() 단일 진입점 사용",
            "LLM 실패는 예외가 아니라 상태로 처리",
        ],
        notes={
            "has_file": has_file,
            "uploaded_files_count": len(uploaded_files),
        },
    )

    events.append(
        evlog(
            "planner.plan",
            "\n".join(
                [
                    f"- intent: {plan.intent}",
                    f"- has_file: {has_file}",
                    f"- uploaded_files: {len(uploaded_files)}",
                    f"- constraints: {', '.join(plan.constraints)}",
                ]
            ),
        )
    )
    events.append(step_end("planner", "계획 수립 완료"))
    return plan, events


async def _execute(sc: StageContext, plan: Plan) -> tuple[ExecutionResult, List[AgentEvent]]:
    events: List[AgentEvent] = []
    artifacts: List[ArtifactRef] = []

    events.append(step_start("executor", "로그/텍스트 수집 및 분석 실행"))

    uploaded_files = _get_uploaded_files(sc.context)

    log_text = ""
    source_note = ""
    file_kind = "text"

    # 1) 파일 우선
    if uploaded_files:
        f0 = uploaded_files[0]
        name, path, ext, mime = _file_name_and_path(f0)

        load_res = load_file(path)
        ok = bool(getattr(load_res, "ok", False))
        summary = getattr(load_res, "summary", None)
        error = getattr(load_res, "error", None)

        data = _get_data(load_res)
        file_kind = str(data.get("kind", "unknown")).lower()

        source_note = (
            f"- file: {name}\n"
            f"- path: {path}\n"
            f"- loader_kind: {file_kind}\n"
            f"- loader_summary: {summary}\n"
        )

        if not ok:
            events.append(
                warn(
                    "executor.file_load_failed",
                    f"파일 로드 실패 → user_message 기반으로 진행 (error={error})",
                )
            )
            log_text = sc.user_message
        else:
            text = data.get("text") or data.get("content") or ""
            if not str(text).strip():
                # text 없으면 preview라도 사용
                preview_csv = data.get("preview_csv", "")
                if preview_csv:
                    text = preview_csv
            log_text = str(text).strip()
            if not log_text:
                events.append(
                    warn(
                        "executor.no_text_from_loader",
                        "로더 결과에 사용 가능한 텍스트가 없어 user_message로 대체합니다.",
                    )
                )
                log_text = sc.user_message
            events.append(info("executor.file_loaded", f"파일 로드 성공: kind={file_kind}"))
    else:
        source_note = "- file: (none)\n- source: user_message\n"
        log_text = sc.user_message
        file_kind = "text"
        events.append(info("executor.no_file", "파일 미첨부 → user_message를 로그 텍스트로 처리"))

    # 2) LLM 시도 (실패 시 rule-based)
    llm_client = LLMClient(sc.settings)
    try:
        system_prompt = load_prompt("agents/logcop/prompts/insight.md")
    except Exception:
        system_prompt = (
            "너는 SRE/플랫폼 엔지니어다. 로그 텍스트를 읽고, "
            "1) 핵심 오류 요약, 2) root cause 후보, 3) 즉시 조치 액션 플랜을 간결한 Markdown으로 작성하라."
        )

    user_prompt = (
        f"[사용자 요청]\n{sc.user_message}\n\n"
        f"[입력]\n{source_note}\n"
        f"[로그(일부)]\n{log_text}\n"
    )

    llm_res = await llm_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    llm_used, llm_status, llm_reason, llm_model = _normalize_llm_meta(llm_res, sc.settings)
    llm_hint_line = ""
    llm_debug_line = ""
    error_code: Optional[str] = None

    if llm_used:
        events.append(info("executor.llm.used", "LLM 인사이트 생성 완료"))
        body = llm_res.content
        llm_hint_line = "- LLM: 적용됨"
    else:
        error_code = llm_res.error
        events.append(warn("executor.llm.skipped", f"{llm_res.content} ({llm_res.error})"))
        body = _rule_based_log_insights(log_text) + "\n\n" + llm_res.content

        if llm_res.error == "network_unreachable":
            llm_hint_line = "- LLM: 미적용 (네트워크 불가)"
        elif llm_res.error == "llm_disabled":
            llm_hint_line = "- LLM: 미적용 (LLM_ENABLED=false)"
        elif llm_res.error == "missing_api_key":
            llm_hint_line = "- LLM: 미적용 (API Key 미설정)"
        else:
            llm_hint_line = "- LLM: 미적용 (호출 실패)"

    report = (
        "# LogCop 분석 보고서\n\n"
        "## 요청\n"
        f"{sc.user_message}\n\n"
        "## 입력\n"
        f"{source_note}\n"
        f"{llm_hint_line}\n"
        "---\n\n"
        f"{body}\n"
        f"{llm_debug_line}\n"
    )

    out_path = _save_markdown(sc.settings, "logcop_report", report)
    artifacts.append(ArtifactRef(kind="markdown", name=out_path.name, path=str(out_path), mime_type="text/markdown"))

    events.append(evlog("executor.done", f"보고서 생성 완료: {out_path.name}"))
    events.append(step_end("executor", "실행 완료"))

    exec_res = ExecutionResult(
        ok=True,
        text="로그 분석 및 보고서 생성 완료",
        artifacts=artifacts,
        llm_used=llm_used,
        file_kind=file_kind,
        error_code=error_code,
        llm_status=llm_status,
        llm_reason=llm_reason,
        llm_model=llm_model,
        debug={
            "loader_kind": file_kind,
            "loader_summary": summary,
            "llm_last_error": getattr(llm_res, "last_error", None),
        },
    )
    return exec_res, events


def _review(sc: StageContext, plan: Plan, exec_res: ExecutionResult) -> tuple[ReviewResult, List[AgentEvent]]:
    events: List[AgentEvent] = []
    events.append(step_start("reviewer", "결과 검증 시작(P2-2-B)"))

    # LogCop 스펙: artifact 1개 + markdown 필수.
    # 로그는 “오류 없음”도 정상 결과일 수 있으므로 placeholder 마커는 최소화.
    spec = ReviewSpec(
        require_artifacts=True,
        min_artifacts=1,
        require_markdown=True,
        markdown_min_chars=50,                  # LogCop은 DIA보다 낮춰도 됨
        markdown_disallow_placeholders=False,   # LogCop은 placeholder 금지 약화
        allow_approve_when_exec_failed=False,
    )

    outcome = review_execution(
        spec=spec,
        exec_ok=bool(exec_res.ok),
        exec_text=exec_res.text,
        artifacts=exec_res.artifacts or [],
        error_code=exec_res.error_code,
        extra={
            "intent": getattr(plan, "intent", None),
            "file_kind": exec_res.file_kind,
        },
    )

    if outcome.approved:
        events.append(info("reviewer.approve", "Reviewer 품질 게이트 통과 → 승인"))
        events.append(evlog("reviewer.details", _format_review_details(outcome.details)))
        events.append(step_end("reviewer", "승인"))
    else:
        events.append(warn("reviewer.reject", "Reviewer 품질 게이트 실패 → 거절"))
        events.append(evlog("reviewer.issues", _format_review_issues(outcome.issues)))
        if outcome.followups:
            events.append(evlog("reviewer.followups", _format_review_followups(outcome.followups)))
        events.append(step_end("reviewer", "거절"))

    return ReviewResult(
        approved=outcome.approved,
        issues=outcome.issues,
        followups=outcome.followups,
    ), events


def _format_review_issues(issues: List[str]) -> str:
    if not issues:
        return "(none)"
    return "\n".join([f"- {x}" for x in issues])


def _format_review_followups(followups: List[str]) -> str:
    if not followups:
        return "(none)"
    return "\n".join([f"- {x}" for x in followups])


def _format_review_details(details: Dict[str, Any]) -> str:
    if not details:
        return "(none)"
    lines = []
    for k in sorted(details.keys()):
        lines.append(f"- {k}: {details[k]}")
    return "\n".join(lines)


async def run_logcop(user_message: str, context: Dict[str, Any], settings: Any) -> AgentResult:
    """
    P2-2-A: Planner/Executor/Reviewer 구조 명확화 버전
    """
    # trace_id는 로깅 레이어에서 이미 처리하지만, meta에는 남길 수 있음
    trace_id = "-"
    if isinstance(context, dict):
        trace_id = str(context.get("session_id") or "-")
    else:
        trace_id = str(getattr(context, "session_id", "-") or "-")

    sc = StageContext(user_message=user_message, context=context, settings=settings, trace_id=trace_id)

    all_events: List[AgentEvent] = []
    all_artifacts: List[ArtifactRef] = []

    plan, ev1 = _plan(sc)
    all_events.extend(ev1)

    exec_res, ev2 = await _execute(sc, plan)
    all_events.extend(ev2)
    all_artifacts.extend(exec_res.artifacts or [])

    review_res, ev3 = _review(sc, plan, exec_res)
    all_events.extend(ev3)

    meta = build_agent_meta(
        agent_id="logcop",
        mode="p2-2-c",
        file_kind=exec_res.file_kind,
        llm_used=exec_res.llm_used,
        artifacts_count=len(all_artifacts),
        approved=review_res.approved,
        error_code=exec_res.error_code,
        llm_status=exec_res.llm_status,
        llm_reason=exec_res.llm_reason,
        llm_model=exec_res.llm_model,
        review_issues=review_res.issues,
        review_followups=review_res.followups,
        trace_id=sc.trace_id,
        extra={
            "debug": exec_res.debug,
        },
    )

    final_text = "LogCop Agent 실행 완료입니다.\n- 산출물을 확인하세요."
    return AgentResult(
        text=final_text,
        events=all_events,
        artifacts=all_artifacts,
        meta=meta,
    )
