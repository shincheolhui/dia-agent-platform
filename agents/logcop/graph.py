# agents/logcop/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt
from core.tools.file_loader import load_file  # ✅ 단일 진입점


def _artifact_dir(settings: Any) -> Path:
    return Path(getattr(settings, "WORKSPACE_DIR", "workspace")) / "artifacts"


def _save_text(settings: Any, title: str, body: str) -> Path:
    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.md"
    out_path = out_dir / filename
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _get_data(load_res: Any) -> dict:
    """
    ToolResult.data를 dict로 안전하게 반환
    """
    data = getattr(load_res, "data", None)
    return data if isinstance(data, dict) else {}


def _get_uploaded_files(context: Any) -> List[Any]:
    """
    Phase2 표준: AgentContext 우선, dict는 fallback
    """
    if context is None:
        return []
    files = getattr(context, "uploaded_files", None)
    if files is not None:
        return files or []
    if isinstance(context, dict):
        return context.get("uploaded_files", []) or []
    return []


def _get_file_field(f: Any, key: str, default: str = "") -> str:
    """
    uploaded_files 요소가 dict/object/dataclass 무엇이든 안전하게 필드를 읽는다.
    """
    if isinstance(f, dict):
        v = f.get(key, default)
    else:
        v = getattr(f, key, default)
    return str(v) if v is not None else str(default)


def _rule_based_log_insights(text: str) -> str:
    lowered = (text or "").lower()
    hits = []
    for k in ["exception", "error", "stacktrace", "traceback", "caused by", "timeout", "pkix", "ssl", "connection"]:
        if k in lowered:
            hits.append(k)

    lines = []
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


async def run_logcop(user_message: str, context: Any, settings: Any) -> AgentResult:
    events: List[AgentEvent] = []
    artifacts: List[ArtifactRef] = []

    uploaded_files = _get_uploaded_files(context)

    events.append(AgentEvent(type="info", name="planner", message="[Planner] 로그 분석 요청을 해석합니다."))
    events.append(AgentEvent(type="info", name="executor", message="[Executor] 로그/텍스트를 수집하고 요약을 생성합니다."))

    log_text = ""
    source_note = ""

    # 1) 파일 우선 (✅ load_file만 사용)
    if uploaded_files:
        f0 = uploaded_files[0]
        path = _get_file_field(f0, "path", "")
        name = _get_file_field(f0, "name", Path(path).name if path else "")

        load_res = load_file(path)
        ok = bool(getattr(load_res, "ok", False))
        summary = getattr(load_res, "summary", None)
        error = getattr(load_res, "error", None)

        data = _get_data(load_res)
        kind = str(data.get("kind", "unknown"))

        source_note = (
            f"- file: {name}\n"
            f"- path: {path}\n"
            f"- loader_kind: {kind}\n"
            f"- loader_summary: {summary}\n"
        )

        if not ok:
            # ✅ P2-1-A 규칙: Agent에서 tail 등 파일 직접 처리는 하지 않는다.
            events.append(
                AgentEvent(
                    type="warning",
                    name="executor.file_loader_failed",
                    message=f"[Executor] 파일 로드 실패 → user_message 기반으로 진행 ({error})",
                )
            )
            log_text = user_message
        else:
            # ✅ TEXT면 text 우선, 그 외엔 text/preview_csv 등을 힌트로라도 사용
            text = data.get("text") or data.get("content") or ""
            if not str(text).strip():
                preview_csv = data.get("preview_csv", "")
                if preview_csv:
                    text = preview_csv

            log_text = str(text).strip()

            if not log_text:
                events.append(
                    AgentEvent(
                        type="warning",
                        name="executor.no_text_from_loader",
                        message="[Executor] 로더 결과에 사용 가능한 텍스트가 없어 user_message로 대체합니다.",
                    )
                )
                log_text = user_message

    else:
        # 2) 파일 없으면 메시지 자체를 로그 텍스트로 취급
        source_note = "- file: (none)\n- source: user_message\n"
        log_text = user_message

    # 3) LLM 시도 (없거나 실패하면 룰 기반)
    llm_client = LLMClient(settings)
    try:
        system_prompt = load_prompt("agents/logcop/prompts/insight.md")
    except Exception:
        system_prompt = (
            "너는 SRE/플랫폼 엔지니어다. 로그 텍스트를 읽고, "
            "1) 핵심 오류 요약, 2) root cause 후보, 3) 즉시 조치 액션 플랜을 간결한 Markdown으로 작성하라."
        )

    user_prompt = (
        f"[사용자 요청]\n{user_message}\n\n"
        f"[입력]\n{source_note}\n"
        f"[로그(일부)]\n{log_text}\n"
    )

    llm_res = await llm_client.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    llm_hint_line = ""
    llm_debug_line = ""

    if llm_res.ok:
        events.append(AgentEvent(type="info", name="executor.llm_used", message="[Executor] LLM 인사이트 생성 완료"))
        body = llm_res.content
        llm_hint_line = "- LLM: 적용됨"
    else:
        events.append(
            AgentEvent(
                type="warning",
                name="executor.llm_fallback",
                message=f"[Executor] {llm_res.content} ({llm_res.error})",
            )
        )

        body = _rule_based_log_insights(log_text) + "\n\n" + llm_res.content

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
                f"\n\n<details><summary>LLM debug</summary>\n\n"
                f"- last_error: {llm_res.last_error}\n\n</details>\n"
            )

    report = (
        "# LogCop 분석 보고서\n\n"
        "## 요청\n"
        f"{user_message}\n\n"
        "## 입력\n"
        f"{source_note}\n"
        f"{llm_hint_line}\n"
        "---\n\n"
        f"{body}\n"
        f"{llm_debug_line}\n"
    )

    out_path = _save_text(settings, "logcop_report", report)
    artifacts.append(ArtifactRef(kind="markdown", name=out_path.name, path=str(out_path)))

    events.append(AgentEvent(type="info", name="reviewer", message="[Reviewer] MVP: 산출물 생성 여부 확인 후 승인"))
    return AgentResult(
        text="LogCop Agent 실행 완료입니다.\n- 산출물을 확인하세요.",
        events=events,
        artifacts=artifacts,
        meta={"agent_id": "logcop", "mode": "mvp"},
    )
