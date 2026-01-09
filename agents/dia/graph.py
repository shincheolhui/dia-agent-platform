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


def _get_from_tool(load_res: Any, key: str, default=None):
    """
    ToolResult / dict / object 모두에서 key를 안전하게 읽는다.
    - 우선 load_res.key
    - 다음 load_res.data[key]
    """
    if isinstance(load_res, dict):
        return load_res.get(key, default)

    if hasattr(load_res, key):
        return getattr(load_res, key, default)

    data = getattr(load_res, "data", None)
    if isinstance(data, dict):
        return data.get(key, default)

    return default


def _tool_kind(load_res: Any, fallback_path: str) -> str:
    data = getattr(load_res, "data", None)
    if isinstance(data, dict) and data.get("kind"):
        return str(data["kind"]).lower()
    k = getattr(load_res, "kind", None)
    if k:
        return str(k).lower()

    ext = Path(fallback_path).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".pdf":
        return "pdf"
    if ext in [".xlsx", ".xls"]:
        return "excel"
    return "unknown"


def _normalize_uploaded_files(context: Any) -> List[Any]:
    """
    context가 AgentContext(표준)든 dict(레거시)든 uploaded_files를 그대로 받아온다.
    여기서는 'list 원본' 유지(UploadedFileRef를 그대로 쓰기 위해).
    """
    if context is None:
        return []
    uf = getattr(context, "uploaded_files", None)
    if uf is not None:
        return list(uf)
    if isinstance(context, dict):
        return list(context.get("uploaded_files") or [])
    return []


def _file_field(f: Any, key: str, default=""):
    """UploadedFileRef / dict 모두 지원"""
    if isinstance(f, dict):
        return f.get(key, default)
    return getattr(f, key, default)


async def run_dia(user_message: str, context: Any, settings: Any) -> AgentResult:
    uploaded_files = _normalize_uploaded_files(context)

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
            "파일(CSV/PDF/XLSX)을 첨부하면 분석 결과를 생성합니다."
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
    file_path = str(_file_field(f0, "path", ""))
    file_name = str(_file_field(f0, "name", Path(file_path).name))

    # ✅ 파일 로딩은 반드시 Tool로
    load_res = load_file(file_path)
    ok = bool(_get_from_tool(load_res, "ok", False))
    kind = _tool_kind(load_res, file_path)
    summary = _get_from_tool(load_res, "summary", None)
    error = _get_from_tool(load_res, "error", None)

    if not ok:
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
            f"- summary: {summary}\n"
        )
        md_path = _save_artifact_markdown(settings, title="dia_file_load_failed", body=body)
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))

        events.append(AgentEvent(type="step_end", name="Executor", message="파일 로드 실패 처리 완료"))
        events.append(AgentEvent(type="step_start", name="Reviewer", message="검증 시작"))
        events.append(AgentEvent(type="log", name="Reviewer", message="로더 실패 케이스: 안내 제공으로 승인"))
        events.append(AgentEvent(type="step_end", name="Reviewer", message="승인"))

        return AgentResult(
            text="DIA Agent 실행 완료입니다. (파일 로드 실패 안내)",
            artifacts=artifacts,
            events=events,
            meta={"agent_id": "dia", "mode": "load_failed", "file_kind": kind},
        )

    events.append(
        AgentEvent(type="info", name="Executor.file_loaded", message=f"파일 로드 성공: kind={kind} {summary or ''}".strip())
    )

    if kind in {"csv", "excel"}:
        data = getattr(load_res, "data", None) or {}
        df = data.get("df")

        if not isinstance(df, pd.DataFrame):
            preview_csv = data.get("preview_csv", "")
            events.append(AgentEvent(type="error", name="Executor.no_dataframe", message="ToolResult에 df가 없습니다. file_loader를 확인하세요."))
            md_path = _save_artifact_markdown(
                settings,
                title="dia_no_dataframe",
                body=(
                    f"# DIA 결과\n\n"
                    f"## 요청\n{user_message}\n\n"
                    f"## 파일\n- name: {file_name}\n- path: {file_path}\n\n"
                    f"## 오류\n- ToolResult에 df가 없어 분석을 진행할 수 없습니다.\n\n"
                    f"## Preview\n```csv\n{preview_csv}\n```\n"
                ),
            )
            artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))

        else:
            head = df.head(10).to_markdown(index=False)
            desc_md = df.describe(include="all").to_markdown()
            plot_path = _save_line_plot(settings, df, title=f"dia_plot_{Path(file_path).stem}")

            llm_client = LLMClient(settings)
            try:
                system_prompt = load_prompt("agents/dia/prompts/insight.md")
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

            if llm_res.ok:
                llm_hint = "- LLM: 적용됨"
                llm_section = ensure_sections(llm_res.content)
                llm_debug = ""
            else:
                llm_section = rule_based_insights(df)

                if llm_res.error == "network_unreachable":
                    llm_hint = "- LLM: 미적용 (폐쇄망/네트워크 제한)"
                elif llm_res.error == "llm_disabled":
                    llm_hint = "- LLM: 미적용 (LLM_ENABLED=false)"
                elif llm_res.error == "missing_api_key":
                    llm_hint = "- LLM: 미적용 (API Key 미설정)"
                else:
                    llm_hint = "- LLM: 미적용 (호출 실패)"

                llm_debug = ""
                if llm_res.last_error:
                    llm_debug = (
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
                    llm_insights_md=(llm_hint + "\n\n" + llm_section + llm_debug),
                )
            )

            md_path = _save_artifact_markdown(settings, title=f"dia_report_{Path(file_path).stem}", body=report_md)
            artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
            if plot_path:
                artifacts.append(ArtifactRef(kind="image", name=plot_path.name, path=str(plot_path), mime_type="image/png"))

            events.append(AgentEvent(type="step_end", name="Executor", message="CSV/Excel 처리 완료"))

    elif kind == "pdf":
        data = getattr(load_res, "data", None) or {}
        text = (data.get("text") or "").strip() or "(텍스트 추출 실패: 스캔 PDF 가능)"

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
                f"## 처리\n지원하지 않는 파일 형식입니다.\n"
                f"- detected_kind: {kind}\n"
                f"- loader_summary: {summary}\n"
            ),
        )
        artifacts.append(ArtifactRef(kind="markdown", name=md_path.name, path=str(md_path), mime_type="text/markdown"))
        events.append(AgentEvent(type="step_end", name="Executor", message="미지원 형식 처리 완료"))

    # Reviewer
    events.append(AgentEvent(type="step_start", name="Reviewer", message="검증 시작"))
    events.append(AgentEvent(type="log", name="Reviewer", message="MVP: 산출물 생성 여부 확인 후 승인"))
    events.append(AgentEvent(type="step_end", name="Reviewer", message="승인"))

    return AgentResult(
        text=f"DIA Agent 실행 완료입니다.\n- 산출물: {len(artifacts)}개\n결과 파일을 확인하세요.",
        artifacts=artifacts,
        events=events,
        meta={"agent_id": "dia", "mode": "mvp", "file_kind": kind},
    )
