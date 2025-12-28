from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import chainlit as cl
import pandas as pd
import pdfplumber
import matplotlib.pyplot as plt

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
    """
    숫자 컬럼을 자동 선택하여 라인 차트 1장을 생성하고 PNG로 저장.
    반환: 생성된 이미지 경로 (없으면 None)
    """
    num_df = df.select_dtypes(include="number")
    if num_df.empty:
        return None

    # 너무 많은 컬럼이면 앞의 2개만 사용 (안정성/가독성)
    cols = list(num_df.columns)[:2]
    plot_df = num_df[cols].head(200)  # 너무 길면 payload/시간 증가 → 상위 200행만

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
    desc = num.describe().T  # columns: count, mean, std, min, 25%, 50%, 75%, max
    # 소수점 정리
    desc = desc.round(3)
    lines = []
    for col in desc.index:
        row = desc.loc[col]
        lines.append(
            f"- {col}: mean={row['mean']}, std={row['std']}, min={row['min']}, p50={row['50%']}, max={row['max']}"
        )
    return "\n".join(lines)


async def run_dia_graph(user_message: str, context: Dict[str, Any], settings: Any):
    """
    MVP+ (해커톤 데모용):
    - 업로드 파일을 workspace/uploads에 저장(앱 레이어에서 수행)
    - Executor가 파일 1개를 실제로 분석
    - 결과를 markdown artifact로 저장하고 다운로드 버튼 제공
    """
    uploaded_files: List[Dict[str, Any]] = context.get("uploaded_files", [])

    # 1) Planner
    async with cl.Step(name="Planner Agent") as s1:
        plan_lines = [
            "요청을 분석하고 작업을 3단계로 분해합니다.",
            f"- 입력: {user_message}",
            "- 계획: 파일 확인 → 분석 실행 → 결과 검증/아티팩트 생성",
        ]
        if uploaded_files:
            plan_lines.append(f"- 첨부 파일: {len(uploaded_files)}개 감지")
        else:
            plan_lines.append("- 첨부 파일: 없음 (텍스트 기반 처리로 진행)")
        s1.output = "\n".join(plan_lines)

    # 2) Executor (실제 처리)
    async with cl.Step(name="Executor Agent") as s2:
        if not uploaded_files:
            exec_out = (
                "첨부된 파일이 없어, 현재 단계에서는 텍스트 기반 안내만 제공합니다.\n"
                "파일(CSV/PDF)을 첨부하면 분석 결과를 생성합니다."
            )
            s2.output = exec_out
            artifact_md = _save_artifact_markdown(
                settings,
                title="dia_no_file_result",
                body=f"# DIA 결과\n\n## 요청\n{user_message}\n\n## 처리\n{exec_out}\n",
            )
        else:
            f0 = uploaded_files[0]
            file_path = f0["path"]
            kind = _detect_kind(file_path)

            if kind == "csv":
                df = pd.read_csv(file_path)
                head = df.head(10).to_markdown(index=False)
                desc = df.describe(include="all").to_markdown()
                plot_path = _save_line_plot(settings, df, title=f"dia_csv_plot_{Path(file_path).stem}")

                # --- LLM 인사이트 생성 (Key 없으면 안전 폴백 메시지 반환) ---
                llm_client = LLMClient(settings)

                # 프롬프트는 파일 기반을 우선 사용, 없으면 기본 프롬프트 사용
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
                    f"[그래프]\n"
                    f"- plot_file: {plot_path.name if plot_path else '(none)'}\n"
                )

                llm_res = await llm_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)

                if llm_res.ok:
                    llm_section = ensure_sections(llm_res.content)
                else:
                    # Key 없을 때도 유의미한 인사이트 제공
                    llm_section = rule_based_insights(df)
                    llm_note = llm_res.content  # "(LLM 비활성...)" 같은 짧은 표식

                s2.output = (
                    f"CSV 파일을 로드했습니다.\n"
                    f"- 파일: {f0['name']}\n"
                    f"- 행/열: {df.shape[0]} x {df.shape[1]}\n\n"
                    "상위 10행과 describe() 요약을 생성합니다."
                )

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

                artifact_md = _save_artifact_markdown(
                    settings,
                    title=f"dia_csv_report_{Path(file_path).stem}",
                    body=report_md,
                )

            elif kind == "pdf":
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    if len(pdf.pages) > 0:
                        text = (pdf.pages[0].extract_text() or "").strip()

                if not text:
                    text = "(첫 페이지에서 텍스트를 추출하지 못했습니다. 스캔 PDF일 수 있습니다.)"

                s2.output = (
                    f"PDF 파일을 로드했습니다.\n"
                    f"- 파일: {f0['name']}\n"
                    f"- 첫 페이지 텍스트 일부를 추출합니다."
                )

                artifact_md = _save_artifact_markdown(
                    settings,
                    title=f"dia_pdf_extract_{Path(file_path).stem}",
                    body=(
                        f"# DIA 분석 결과 (PDF)\n\n"
                        f"## 요청\n{user_message}\n\n"
                        f"## 파일\n- name: {f0['name']}\n- path: {file_path}\n\n"
                        f"## 첫 페이지 텍스트\n\n{text}\n"
                    ),
                )

            else:
                s2.output = (
                    f"지원하지 않는 파일 형식입니다.\n"
                    f"- 파일: {f0['name']}\n"
                    f"- path: {file_path}\n\n"
                    "현재 MVP에서는 CSV/PDF만 처리합니다."
                )
                artifact_md = _save_artifact_markdown(
                    settings,
                    title="dia_unsupported_file",
                    body=(
                        f"# DIA 결과\n\n## 요청\n{user_message}\n\n"
                        f"## 파일\n- name: {f0['name']}\n- path: {file_path}\n\n"
                        "## 처리\n지원하지 않는 파일 형식입니다. (CSV/PDF만 지원)\n"
                    ),
                )

    # 3) Reviewer
    async with cl.Step(name="Reviewer Agent") as s3:
        s3.output = "결과 아티팩트를 생성했습니다. ✅ 승인"

    # 4) 최종 응답 + 다운로드 버튼
    elements = [
        cl.File(name=artifact_md.name, path=str(artifact_md), display="inline"),
    ]

    # 그래프가 생성된 경우: 이미지 미리보기 + 다운로드 제공
    if "plot_path" in locals() and plot_path is not None:
        elements.append(
            cl.Image(
                name=plot_path.name,
                path=str(plot_path),
                display="inline",
            )
        )

    plot_note = ""
    if "plot_path" in locals() and plot_path is not None:
        plot_note = f"\n- 생성 그래프: {plot_path.name}"

    llm_hint = ""
    if not llm_res.ok and llm_res.error == "missing_api_key":
        llm_hint = "\n- 참고: OPENROUTER_API_KEY 설정 시 LLM 기반 인사이트가 자동 생성됩니다."

    final_text = (
        "DIA Agent 실행 완료입니다.\n\n"
        f"- 요청: {user_message}\n"
        f"- 생성 아티팩트: {artifact_md.name}\n"
        f"{plot_note}\n"
        f"{llm_hint}\n\n"
        "아래 파일 버튼으로 결과를 다운로드할 수 있습니다."
    )
    return {"text": final_text, "elements": elements}
