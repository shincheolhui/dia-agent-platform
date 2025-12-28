from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReportInputs:
    user_request: str
    file_name: str
    file_path: str
    shape: Optional[str] = None
    head_md: Optional[str] = None
    describe_md: Optional[str] = None
    plot_file: Optional[str] = None
    llm_insights_md: Optional[str] = None


def build_markdown_report(inp: ReportInputs) -> str:
    parts: list[str] = []
    parts.append("# DIA 분석 보고서\n")
    parts.append("## 요청\n")
    parts.append(f"{inp.user_request}\n")

    parts.append("## 입력 파일\n")
    parts.append(f"- name: {inp.file_name}\n- path: {inp.file_path}\n")
    if inp.shape:
        parts.append(f"- shape: {inp.shape}\n")
    if inp.plot_file:
        parts.append(f"- plot: {inp.plot_file}\n")

    if inp.llm_insights_md:
        parts.append("\n---\n")
        parts.append("## 자동 인사이트(LLM)\n")
        parts.append(inp.llm_insights_md.strip() + "\n")

    if inp.head_md:
        parts.append("\n---\n")
        parts.append("## 상위 10행\n")
        parts.append(inp.head_md + "\n")

    if inp.describe_md:
        parts.append("\n---\n")
        parts.append("## describe()\n")
        parts.append(inp.describe_md + "\n")

    return "\n".join(parts)
