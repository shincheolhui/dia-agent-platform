# agents/dia/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import matplotlib.pyplot as plt

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
    # ✅ P2-2-A: UploadedFileRef/dict 혼용 안전 접근 헬퍼 (stages.py에 이미 추가했다고 하셨음)
    _file_get,
    _file_name_and_path,
)
from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt, default_insight_prompt
from core.llm.validators import ensure_sections
from core.tools.file_loader import load_file

from agents.dia.report import ReportInputs, build_markdown_report
from agents.dia.insights import rule_based_insights


def _artifact_dir(settings: Any) -> Path:
    return Path(getattr(settings, "WORKSPACE_DIR", "workspace")) / "artifacts"


def _save_artifact_markdown(settings: Any, title: str, body: str) -> Path:
    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.md"
    out_path = out_dir / filename
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _save_line_plot(settings: Any, df: pd.DataFrame, title: str) -> Path | None:
    num_df = df.select_dtypes(include="number")
    if num_df.empty:
        return None

    cols = list(num_df.columns)[:2]
    plot_df = num_df[cols].head(200)

    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.png"
    out_path = out_dir / filename

    plt.figure()
    plot_df.plot()
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def _summarize_numeric(df: pd.DataFrame) -> str:
    num = df.select_dtypes(include="number")
    if num.empty:
        return "(숫자 컬럼 없음)"
    desc = num.describe().T.round(3)
    lines = []
    for col in desc.index:
        row = desc.loc[col]
        lines.append(
            f"- {col}: mean={row['mean']}, std={row['std']}, min={row['min']}, p50={row['50%']}, max={row['max']}"
        )
    return "\n".join(lines)


def _coerce_kind(load_res: Any, fallback_path: str) -> str:
    kind = None
    if isinstance(load_res, dict):
        kind = load_res.get("kind")
    else:
        kind = getattr(load_res, "kind", None)

    if kind:
        return str(kind).lower()

    ext = Path(fallback_path).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".pdf":
        return "pdf"
    return "unknown"


def _get_attr(load_res: Any, key: str, default=None):
    if isinstance(load_res, dict):
        return load_res.get(key, default)
    return getattr(load_res, key, default)


def _get_uploaded_files(context: Any) -> List[Any]:
    """
    context가 dict(구버전) 또는 AgentContext(신버전)일 수 있으므로
    uploaded_files를 list로 안전하게 반환한다.
    - elements는 dict 또는 UploadedFileRef가 될 수 있음 (✅ stages.py 헬퍼로 접근)
    """
    if isinstance(context, dict):
        v = context.get("uploaded_files", []) or []
        return v if isinstance(v, list) else []
    v = getattr(context, "uploaded_files", None) or []
    return v if isinstance(v, list) else []


def _plan(sc: StageContext) -> tuple[Plan, List[AgentEvent]]:
    events: List[AgentEvent] = []
    events.append(step_start("planner", "요청 해석 및 작업 분해 시작"))

    uploaded_files = _get_uploaded_files(sc.context)
    has_file = bool(uploaded_files)

    notes: Dict[str, Any] = {"has_file": has_file, "uploaded_files_count": len(uploaded_files)}
    if has_file:
        f0 = uploaded_files[0]
        file_name, file_path = _file_name_and_path(f0)
        notes["first_file_name"] = file_name
        notes["first_file_path"] = file_path
        notes["first_file_ext"] = str(Path(str(file_path or "")).suffix).lower()
        notes["first_file_mime"] = _file_get(f0, "mime")

    plan = Plan(
        intent="data_inspection",
        assumptions=[
            "CSV/PDF 입력을 우선 지원",
            "LLM은 설정/네트워크에 따라 비활성 또는 실패할 수 있음",
        ],
        constraints=[
            "파일 로딩은 load_file() 단일 진입점 사용",
            "LLM 실패는 예외가 아니라 상태로 처리",
        ],
        notes=notes,
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
    llm_used = False
    error_code: Optional[str] = None

    events.append(step_start("executor", "파일 확인 및 분석 실행"))

    uploaded_files = _get_uploaded_files(sc.context)

    if not uploaded_files:
        body = (
            "# DIA 결과\n\n"
            f"## 요청\n{sc.user_message}\n\n"
            "## 처리\n"
            "첨부된 파일이 없어, 현재 단계에서는 텍스트 기반 안내만 제공합니다.\n"
            "파일(CSV/PDF)을 첨부하면 분석 결과를 생성합니다.\n"
        )
        md_path = _save_artifact_markdown(sc.settings, "dia_no_file_result", body)
        artifacts.append(
            ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
        )

        events.append(info("executor.no_file", "파일 미첨부 처리: 안내 문서 생성"))
        events.append(step_end("executor", "실행 완료"))

        return (
            ExecutionResult(
                ok=True,
                text="파일 미첨부 안내",
                artifacts=artifacts,
                llm_used=False,
                file_kind="none",
                error_code=None,
            ),
            events,
        )

    # MVP: 파일 1개 처리
    f0 = uploaded_files[0]

    # ✅ dict / UploadedFileRef 모두 대응 (stages.py 헬퍼)
    file_name, file_path = _file_name_and_path(f0)

    load_res = load_file(file_path)
    ok = bool(_get_attr(load_res, "ok", False))
    kind = _coerce_kind(load_res, file_path)
    summary = _get_attr(load_res, "summary", None)
    error = _get_attr(load_res, "error", None)

    if not ok:
        events.append(warn("executor.file_load_failed", f"파일 로드 실패: {error or 'unknown_error'}"))
        body = (
            f"# DIA 결과\n\n"
            f"## 요청\n{sc.user_message}\n\n"
            f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
            f"## 처리\n"
            f"- 파일 로드에 실패했습니다.\n"
            f"- error: {error}\n"
            f"- summary: {summary}\n\n"
            f"### 권장 액션\n"
            f"- 파일이 열려있다면 닫고 다시 업로드\n"
            f"- CSV 인코딩(UTF-8/CP949) 확인\n"
            f"- 파일 크기가 매우 크면 일부만 샘플로 줄여 업로드\n"
        )
        md_path = _save_artifact_markdown(sc.settings, "dia_file_load_failed", body)
        artifacts.append(
            ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
        )

        events.append(step_end("executor", "실행 완료(로드 실패 안내)"))
        return (
            ExecutionResult(
                ok=False,
                text="파일 로드 실패 안내",
                artifacts=artifacts,
                llm_used=False,
                file_kind=kind,
                error_code="file_load_failed",
            ),
            events,
        )

    events.append(info("executor.file_loaded", f"파일 로드 성공: kind={kind} / {summary or ''}".strip()))

    # -------------------
    # kind별 처리
    # -------------------
    if kind == "csv":
        df = _get_attr(load_res, "df", None)
        if df is None:
            df = _get_attr(load_res, "dataframe", None)

        if df is None or not isinstance(df, pd.DataFrame):
            preview_csv = _get_attr(load_res, "preview_csv", "")
            events.append(
                warn("executor.csv_no_dataframe", "CSV로 인식되었으나 DataFrame이 없어 preview 기반으로 처리합니다.")
            )

            md_path = _save_artifact_markdown(
                sc.settings,
                "dia_csv_preview_only",
                (
                    "# DIA 결과 (CSV Preview)\n\n"
                    f"## 요청\n{sc.user_message}\n\n"
                    f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                    f"## Preview\n\n```csv\n{preview_csv}\n```\n"
                ),
            )
            artifacts.append(
                ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
            )
            events.append(step_end("executor", "실행 완료(CSV preview)"))
            return (
                ExecutionResult(
                    ok=True,
                    text="CSV preview 처리 완료",
                    artifacts=artifacts,
                    llm_used=False,
                    file_kind="csv",
                ),
                events,
            )

        head = df.head(10).to_markdown(index=False)
        desc_md = df.describe(include="all").to_markdown()
        plot_path = _save_line_plot(sc.settings, df, title=f"dia_csv_plot_{Path(file_path).stem}")

        llm_client = LLMClient(sc.settings)
        prompt_path = "agents/dia/prompts/insight.md"
        try:
            system_prompt = load_prompt(prompt_path)
        except Exception:
            system_prompt = default_insight_prompt()

        numeric_summary = _summarize_numeric(df)
        user_prompt = (
            f"[사용자 요청]\n{sc.user_message}\n\n"
            f"[데이터 개요]\n"
            f"- file: {file_name}\n"
            f"- shape: {df.shape[0]} x {df.shape[1]}\n"
            f"- columns: {', '.join(map(str, df.columns.tolist()))}\n\n"
            f"[숫자 컬럼 요약]\n{numeric_summary}\n\n"
            f"[상위 10행]\n{df.head(10).to_csv(index=False)}\n\n"
            f"[그래프]\n- plot_file: {plot_path.name if plot_path else '(none)'}\n"
        )

        llm_res = await llm_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)

        llm_hint_line = ""
        llm_debug_line = ""

        if llm_res.ok:
            llm_used = True
            events.append(info("executor.llm.used", "LLM 인사이트 생성 완료"))
            llm_section = ensure_sections(llm_res.content)
            llm_hint_line = "- LLM: 적용됨"
        else:
            error_code = llm_res.error
            events.append(warn("executor.llm.skipped", f"{llm_res.content} ({llm_res.error})"))
            llm_section = rule_based_insights(df)

            if llm_res.error == "network_unreachable":
                llm_hint_line = "- LLM: 미적용 (폐쇄망/네트워크 제한)"
            elif llm_res.error == "llm_disabled":
                llm_hint_line = "- LLM: 미적용 (LLM_ENABLED=false)"
            elif llm_res.error == "missing_api_key":
                llm_hint_line = "- LLM: 미적용 (API Key 미설정)"
            else:
                llm_hint_line = "- LLM: 미적용 (호출 실패)"

            if llm_res.last_error:
                llm_debug_line = (
                    "\n\n<details><summary>LLM debug</summary>\n\n"
                    f"- last_error: {llm_res.last_error}\n\n</details>\n"
                )

        report_md = build_markdown_report(
            ReportInputs(
                user_request=sc.user_message,
                file_name=file_name,
                file_path=file_path,
                shape=f"{df.shape[0]} x {df.shape[1]}",
                head_md=head,
                describe_md=desc_md,
                plot_file=(plot_path.name if plot_path else None),
                llm_insights_md=(llm_hint_line + "\n\n" + llm_section + llm_debug_line),
            )
        )

        md_path = _save_artifact_markdown(sc.settings, f"dia_csv_report_{Path(file_path).stem}", report_md)
        artifacts.append(
            ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
        )

        if plot_path is not None:
            artifacts.append(ArtifactRef(kind="image", name=plot_path.name, path=str(plot_path), mime_type="image/png"))

        events.append(evlog("executor.done", "CSV 처리 완료: 보고서/그래프 생성"))
        events.append(step_end("executor", "실행 완료"))

        return (
            ExecutionResult(
                ok=True,
                text="CSV 분석 완료",
                artifacts=artifacts,
                llm_used=llm_used,
                file_kind="csv",
                error_code=error_code,
            ),
            events,
        )

    if kind == "pdf":
        text = _get_attr(load_res, "text", "") or _get_attr(load_res, "content", "") or ""
        text = str(text).strip() if text else ""
        if not text:
            text = "(텍스트 추출 실패: 스캔 PDF 가능)"

        md_path = _save_artifact_markdown(
            sc.settings,
            f"dia_pdf_extract_{Path(file_path).stem}",
            (
                "# DIA 분석 결과 (PDF)\n\n"
                f"## 요청\n{sc.user_message}\n\n"
                f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                "## 텍스트(발췌)\n\n"
                f"{text}\n"
            ),
        )
        artifacts.append(
            ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
        )
        events.append(step_end("executor", "실행 완료(PDF 처리)"))

        return (
            ExecutionResult(
                ok=True,
                text="PDF 처리 완료",
                artifacts=artifacts,
                llm_used=False,
                file_kind="pdf",
            ),
            events,
        )

    # unsupported
    md_path = _save_artifact_markdown(
        sc.settings,
        "dia_unsupported_file",
        (
            "# DIA 결과\n\n"
            f"## 요청\n{sc.user_message}\n\n"
            f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
            "## 처리\n지원하지 않는 파일 형식입니다. (CSV/PDF만 지원)\n"
            f"- detected_kind: {kind}\n"
            f"- loader_summary: {summary}\n"
        ),
    )
    artifacts.append(
        ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown")
    )
    events.append(step_end("executor", "실행 완료(미지원 형식)"))

    return (
        ExecutionResult(
            ok=False,
            text="미지원 형식 안내",
            artifacts=artifacts,
            llm_used=False,
            file_kind=kind,
            error_code="unsupported_file_kind",
        ),
        events,
    )


def _review(sc: StageContext, plan: Plan, exec_res: ExecutionResult) -> tuple[ReviewResult, List[AgentEvent]]:
    events: List[AgentEvent] = []
    events.append(step_start("reviewer", "결과 검증 시작"))

    issues: List[str] = []
    followups: List[str] = []

    # MVP Lite 게이트(실질화는 P2-2-B에서 강화)
    if not exec_res.artifacts:
        issues.append("산출물이 생성되지 않았습니다.")
        followups.append("CSV 또는 PDF 파일을 다시 업로드해 주세요.")
    else:
        # markdown 산출물 최소 1개는 있어야 함
        has_md = any((a.kind == "markdown") for a in (exec_res.artifacts or []))
        if not has_md:
            issues.append("Markdown 보고서 산출물이 없습니다.")

    approved = len(issues) == 0
    if approved:
        events.append(info("reviewer.approve", "MVP: 산출물 생성 확인 → 승인"))
        events.append(step_end("reviewer", "승인"))
    else:
        events.append(warn("reviewer.reject", "품질 게이트 실패"))
        events.append(evlog("reviewer.issues", "\n".join(f"- {x}" for x in issues)))
        events.append(step_end("reviewer", "거절"))

    return ReviewResult(approved=approved, issues=issues, followups=followups), events


async def run_dia(user_message: str, context: Dict[str, Any], settings: Any) -> AgentResult:
    """
    P2-2-A: Planner/Executor/Reviewer 구조 명확화 버전
    """
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
        agent_id="dia",
        mode="p2-2-a",
        file_kind=exec_res.file_kind,
        llm_used=exec_res.llm_used,
        artifacts_count=len(all_artifacts),
        approved=review_res.approved,
        error_code=exec_res.error_code,
        extra={
            "trace_id": sc.trace_id,
            "review_issues": review_res.issues,
        },
    )

    final_text = (
        "DIA Agent 실행 완료입니다.\n\n"
        f"- 요청: {user_message}\n"
        f"- 산출물: {len(all_artifacts)}개\n"
        "결과 파일을 확인하세요."
    )

    return AgentResult(
        text=final_text,
        artifacts=all_artifacts,
        events=all_events,
        meta=meta,
    )
