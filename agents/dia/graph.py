# agents/dia/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pdfplumber
import matplotlib.pyplot as plt

from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt, default_insight_prompt
from core.llm.validators import ensure_sections
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


def _detect_kind(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".pdf":
        return "pdf"
    return "unknown"


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
    file_path = f0["path"]
    kind = _detect_kind(file_path)

    if kind == "csv":
        df = pd.read_csv(file_path)
        head = df.head(10).to_markdown(index=False)
        desc = df.describe(include="all").to_markdown()
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
            f"- file: {f0['name']}\n"
            f"- shape: {df.shape[0]} x {df.shape[1]}\n"
            f"- columns: {', '.join(map(str, df.columns.tolist()))}\n\n"
            f"[숫자 컬럼 요약]\n{numeric_summary}\n\n"
            f"[상위 10행]\n{df.head(10).to_csv(index=False)}\n\n"
            f"[그래프]\n- plot_file: {plot_path.name if plot_path else '(none)'}\n"
        )

        llm_res = await llm_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)
        if llm_res.ok:
            llm_section = ensure_sections(llm_res.content)
        else:
            llm_section = rule_based_insights(df)

        report_md = build_markdown_report(
            ReportInputs(
                user_request=user_message,
                file_name=f0["name"],
                file_path=file_path,
                shape=f"{df.shape[0]} x {df.shape[1]}",
                head_md=head,
                describe_md=desc,
                plot_file=(plot_path.name if plot_path else None),
                llm_insights_md=llm_section,
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
        text = ""
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > 0:
                text = (pdf.pages[0].extract_text() or "").strip()
        if not text:
            text = "(첫 페이지 텍스트 추출 실패: 스캔 PDF 가능)"

        md_path = _save_artifact_markdown(
            settings,
            title=f"dia_pdf_extract_{Path(file_path).stem}",
            body=(
                f"# DIA 분석 결과 (PDF)\n\n"
                f"## 요청\n{user_message}\n\n"
                f"## 파일\n- name: {f0['name']}\n- path: {file_path}\n\n"
                f"## 첫 페이지 텍스트\n\n{text}\n"
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
                f"## 파일\n- name: {f0['name']}\n- path: {file_path}\n\n"
                "## 처리\n지원하지 않는 파일 형식입니다. (CSV/PDF만 지원)\n"
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
