# agents/dia/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import matplotlib.pyplot as plt

from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt, default_insight_prompt
from core.llm.validators import ensure_sections
from core.tools.file_loader import load_file  # ✅ 단일 진입점

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
    """
    load_file 결과 객체/딕셔너리 모두 지원.
    kind가 없으면 확장자로 추정(최후 fallback).
    """
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


async def run_dia(user_message: str, context: Dict[str, Any], settings: Any) -> AgentResult:
    uploaded_files: List[Dict[str, Any]] = context.get("uploaded_files", [])
    events: List[AgentEvent] = []
    artifacts: List[ArtifactRef] = []

    # Planner
    events.append(AgentEvent(type="step_start", name="Planner", message="요청 해석 및 작업 분해 시작"))
    plan_lines = [
        "요청을 분석하고 작업을 3단계로 분해합니다.",
        f"- 입력: {user_message}",
        "- 계획: 파일 확인 → 분석 실행 → 결과 검증/아티팩트 생성",
    ]
    plan_lines.append(f"- 첨부 파일: {len(uploaded_files)}개 감지" if uploaded_files else "- 첨부 파일: 없음")
    events.append(AgentEvent(type="log", name="Planner.plan", message="\n".join(plan_lines)))
    events.append(AgentEvent(type="step_end", name="Planner", message="계획 수립 완료"))

    # Executor
    events.append(AgentEvent(type="step_start", name="Executor", message="실행 시작"))

    if not uploaded_files:
        exec_out = (
            "첨부된 파일이 없어, 현재 단계에서는 텍스트 기반 안내만 제공합니다.\n"
            "파일(CSV/PDF)을 첨부하면 분석 결과를 생성합니다."
        )
        md_path = _save_artifact_markdown(
            settings,
            title="dia_no_file_result",
            body=f"# DIA 결과\n\n## 요청\n{user_message}\n\n## 처리\n{exec_out}\n",
        )
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
        events.append(AgentEvent(type="step_end", name="Executor", message="파일 없음 처리 완료"))

        # Reviewer
        events.append(AgentEvent(type="step_start", name="Reviewer", message="검증 시작"))
        events.append(AgentEvent(type="log", name="Reviewer", message="파일 미첨부 케이스: 안내 문구 반환으로 승인"))
        events.append(AgentEvent(type="step_end", name="Reviewer", message="승인"))

        return AgentResult(
            text="DIA Agent 실행 완료입니다. (파일 미첨부 안내)",
            artifacts=artifacts,
            events=events,
            meta={"agent_id": "dia", "mode": "no_file"},
        )

    # 파일 1개 MVP 처리
    f0 = uploaded_files[0]
    file_path = str(f0.get("path", ""))
    file_name = str(f0.get("name", Path(file_path).name))

    # ✅ 파일 로딩은 반드시 Tool로
    load_res = load_file(file_path)
    ok = bool(_get_attr(load_res, "ok", False))
    kind = _coerce_kind(load_res, file_path)
    summary = _get_attr(load_res, "summary", None)
    error = _get_attr(load_res, "error", None)

    if not ok:
        # 로더 실패 UX
        events.append(
            AgentEvent(
                type="error",
                name="Executor.file_loader_failed",
                message=f"파일 로드 실패: {error or 'unknown_error'}",
            )
        )
        body = (
            f"# DIA 결과\n\n"
            f"## 요청\n{user_message}\n\n"
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
        md_path = _save_artifact_markdown(settings, title="dia_file_load_failed", body=body)
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))

        events.append(AgentEvent(type="step_end", name="Executor", message="파일 로드 실패 처리 완료"))
        events.append(AgentEvent(type="step_start", name="Reviewer", message="검증 시작"))
        events.append(AgentEvent(type="log", name="Reviewer", message="로더 실패 케이스: 안내/조치 가이드 제공으로 승인"))
        events.append(AgentEvent(type="step_end", name="Reviewer", message="승인"))

        return AgentResult(
            text="DIA Agent 실행 완료입니다. (파일 로드 실패 안내)",
            artifacts=artifacts,
            events=events,
            meta={"agent_id": "dia", "mode": "load_failed", "kind": kind},
        )

    events.append(
        AgentEvent(
            type="info",
            name="Executor.file_loaded",
            message=f"파일 로드 성공: kind={kind} / {summary or ''}".strip(),
        )
    )

    if kind == "csv":
        # load_file 결과에서 DF 추출 (구현체 차이를 흡수)
        df = _get_attr(load_res, "df", None)
        if df is None:
            df = _get_attr(load_res, "dataframe", None)

        if df is None or not isinstance(df, pd.DataFrame):
            # CSV인데 DF가 없다면: preview_csv라도 있으면 안내로 대체
            preview_csv = _get_attr(load_res, "preview_csv", "")
            events.append(
                AgentEvent(
                    type="warning",
                    name="Executor.csv_no_dataframe",
                    message="CSV로 인식되었으나 DataFrame이 없어 preview 기반으로 처리합니다.",
                )
            )
            md_path = _save_artifact_markdown(
                settings,
                title="dia_csv_preview_only",
                body=(
                    f"# DIA 결과 (CSV Preview)\n\n"
                    f"## 요청\n{user_message}\n\n"
                    f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                    f"## Preview\n\n```csv\n{preview_csv}\n```\n"
                ),
            )
            artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
            events.append(AgentEvent(type="step_end", name="Executor", message="CSV preview 처리 완료"))

        else:
            head = df.head(10).to_markdown(index=False)
            desc_md = df.describe(include="all").to_markdown()
            plot_path = _save_line_plot(settings, df, title=f"dia_csv_plot_{Path(file_path).stem}")

            # LLM 인사이트 (없으면 rule-based)
            llm_client = LLMClient(settings)
            prompt_path = "agents/dia/prompts/insight.md"
            try:
                system_prompt = load_prompt(prompt_path)
            except Exception:
                system_prompt = default_insight_prompt()

            numeric_summary = _summarize_numeric(df)
            user_prompt = (
                f"[사용자 요청]\n{user_message}\n\n"
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
                events.append(AgentEvent(type="info", name="executor.llm_used", message="[Executor] LLM 인사이트 생성 완료"))
                llm_section = ensure_sections(llm_res.content)
                llm_hint_line = "- LLM: 적용됨"
            else:
                events.append(
                    AgentEvent(
                        type="warning",
                        name="executor.llm_fallback",
                        message=f"[Executor] {llm_res.content} ({llm_res.error})",
                    )
                )

                llm_section = rule_based_insights(df)

                if llm_res.error == "network_unreachable":
                    llm_hint_line = "- LLM: 미적용 (폐쇄망/네트워크 제한)"
                elif llm_res.error == "llm_disabled":
                    llm_hint_line = "- LLM: 미적용 (LLM_ENABLED=false)"
                elif llm_res.error == "missing_api_key":
                    llm_hint_line = "- LLM: 미적용 (API Key 미설정)"
                else:
                    llm_hint_line = "- LLM: 미적용 (호출 실패)"

                # last_error는 UI에 노출하지 않고 보고서 하단에만 선택적으로 남김
                llm_debug_line = ""
                if llm_res.last_error:
                    llm_debug_line = (
                        f"\n\n<details><summary>LLM debug</summary>\n\n"
                        f"- last_error: {llm_res.last_error}\n\n</details>\n"
                    )

            report_md = build_markdown_report(
                ReportInputs(
                    user_request=user_message,
                    file_name=file_name,
                    file_path=file_path,
                    shape=f"{df.shape[0]} x {df.shape[1]}",
                    head_md=head,
                    describe_md=desc_md,
                    plot_file=(plot_path.name if plot_path else None),
                    llm_insights_md=(llm_hint_line + "\n\n" + llm_section + llm_debug_line),
                )
            )

            md_path = _save_artifact_markdown(
                settings,
                title=f"dia_csv_report_{Path(file_path).stem}",
                body=report_md,
            )
            artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))

            if plot_path is not None:
                artifacts.append(ArtifactRef(kind="image", name=plot_path.name, path=str(plot_path), mime_type="image/png"))

            events.append(AgentEvent(type="log", name="Executor", message="CSV 처리 완료: 보고서/그래프 생성"))
            events.append(AgentEvent(type="step_end", name="Executor", message="실행 완료"))

    elif kind == "pdf":
        # load_file 결과에서 text 추출
        text = _get_attr(load_res, "text", "") or _get_attr(load_res, "content", "") or ""
        text = str(text).strip() if text else ""

        if not text:
            text = "(텍스트 추출 실패: 스캔 PDF 가능)"

        md_path = _save_artifact_markdown(
            settings,
            title=f"dia_pdf_extract_{Path(file_path).stem}",
            body=(
                f"# DIA 분석 결과 (PDF)\n\n"
                f"## 요청\n{user_message}\n\n"
                f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                f"## 텍스트(발췌)\n\n{text}\n"
            ),
        )
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
        events.append(AgentEvent(type="step_end", name="Executor", message="PDF 처리 완료"))

    else:
        md_path = _save_artifact_markdown(
            settings,
            title="dia_unsupported_file",
            body=(
                f"# DIA 결과\n\n## 요청\n{user_message}\n\n"
                f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                f"## 처리\n지원하지 않는 파일 형식입니다. (CSV/PDF만 지원)\n"
                f"- detected_kind: {kind}\n"
                f"- loader_summary: {summary}\n"
            ),
        )
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
        events.append(AgentEvent(type="step_end", name="Executor", message="미지원 형식 처리 완료"))

    # Reviewer (현재는 MVP 승인)
    events.append(AgentEvent(type="step_start", name="Reviewer", message="검증 시작"))
    events.append(AgentEvent(type="log", name="Reviewer", message="MVP: 산출물 생성 여부 확인 후 승인"))
    events.append(AgentEvent(type="step_end", name="Reviewer", message="승인"))

    final_text = (
        "DIA Agent 실행 완료입니다.\n\n"
        f"- 요청: {user_message}\n"
        f"- 산출물: {len(artifacts)}개\n"
        "결과 파일을 확인하세요."
    )

    return AgentResult(
        text=final_text,
        artifacts=artifacts,
        events=events,
        meta={"agent_id": "dia", "mode": "mvp"},
    )
