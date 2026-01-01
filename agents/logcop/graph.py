from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.artifacts.types import AgentEvent, AgentResult, ArtifactRef
from core.utils.fs import ensure_dir, safe_filename
from core.utils.time import ts

from core.llm.client import LLMClient
from core.llm.prompts import load_prompt


def _artifact_dir(settings: Any) -> Path:
    return Path(getattr(settings, "WORKSPACE_DIR", "workspace")) / "artifacts"


def _save_text(settings: Any, title: str, body: str) -> Path:
    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.md"
    out_path = out_dir / filename
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _detect_text_file(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in [".log", ".txt", ".out"]


def _read_tail(path: str, max_chars: int = 20000) -> str:
    p = Path(path)
    if not p.exists():
        return f"(file not found: {path})"
    data = p.read_text(encoding="utf-8", errors="replace")
    if len(data) <= max_chars:
        return data
    return data[-max_chars:]


def _rule_based_log_insights(text: str) -> str:
    # 아주 단순한 MVP 규칙 기반
    lowered = text.lower()
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


async def run_logcop(user_message: str, context: Dict[str, Any], settings: Any) -> AgentResult:
    events: List[AgentEvent] = []
    artifacts: List[ArtifactRef] = []

    uploaded_files: List[Dict[str, Any]] = context.get("uploaded_files", []) or []
    events.append(AgentEvent(type="info", name="planner", message="[Planner] 로그 분석 요청을 해석합니다."))
    events.append(AgentEvent(type="info", name="executor", message="[Executor] 로그/텍스트를 수집하고 요약을 생성합니다."))

    log_text = ""
    source_note = ""

    # 1) 파일 우선
    if uploaded_files:
        f0 = uploaded_files[0]
        path = str(f0.get("path", ""))
        if _detect_text_file(path):
            log_text = _read_tail(path)
            source_note = f"- file: {f0.get('name')}\n- path: {path}\n"
        else:
            # 텍스트 파일이 아니면 그냥 텍스트 기반 처리로 전환
            source_note = f"- uploaded_file: {f0.get('name')} (non-log)\n- path: {path}\n"
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
    if llm_res.ok:
        body = llm_res.content
    else:
        events.append(
            AgentEvent(
                type="warning",
                name="executor.llm_fallback",
                message=f"[Executor] LLM 실패 → rule-based fallback 사용 ({llm_res.error})",
            )
        )
        body = _rule_based_log_insights(log_text) + "\n\n" + llm_res.content

    report = (
        "# LogCop 분석 보고서\n\n"
        "## 요청\n"
        f"{user_message}\n\n"
        "## 입력\n"
        f"{source_note}\n"
        "---\n\n"
        f"{body}\n"
    )

    out_path = _save_text(settings, "logcop_report", report)
    artifacts.append(ArtifactRef(kind="markdown", name=out_path.name, path=str(out_path)))

    events.append(AgentEvent(type="info", name="reviewer", message="[Reviewer] MVP: 산출물 생성 여부 확인 후 승인"))
    return AgentResult(
        text="LogCop Agent 실행 완료입니다.\n- 산출물을 확인하세요.",
        events=events,
        artifacts=artifacts,
    )