# apps/chainlit_app/ui/render.py
from __future__ import annotations

from typing import Any, List, Optional

import chainlit as cl

from core.artifacts.types import AgentResult, ArtifactRef, AgentEvent


# ----------------------------
# Safe getters (dict / object)
# ----------------------------
def _ev_get(ev: Any, key: str, default=None):
    if isinstance(ev, dict):
        return ev.get(key, default)
    return getattr(ev, key, default)


def _meta_get(meta: Any, path: List[str], default=None):
    """
    meta(dict)에서 nested path를 안전하게 가져온다.
    예: _meta_get(meta, ["llm", "status"], "-")
    """
    cur = meta
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# ----------------------------
# Event type inference
# ----------------------------
def _infer_event_type(ev: Any) -> str:
    """
    AgentEvent가 dict 형태로 오면서 'type'이 없을 수 있다.
    이 프로젝트에서는 name이 'planner.start' / 'planner.end' 형태로 생성되는 경우가 있으므로
    name suffix로 step start/end를 추론한다.
    """
    ev_type = _ev_get(ev, "type", None)
    if isinstance(ev_type, str) and ev_type.strip():
        return ev_type.strip()

    name = _ev_get(ev, "name", "")
    if not isinstance(name, str):
        return "log"

    # stages.py에서 step_start/step_end를 f"{step}.start", f"{step}.end" 로 만드는 경우 대응
    if name.endswith(".start"):
        return "step_start"
    if name.endswith(".end"):
        return "step_end"

    return "log"


def _infer_step_name(ev: Any) -> str:
    """
    step 이벤트 표시용 name.
    - ev.name이 'planner.start'면 'planner'만 보여주는 편이 보기 좋다.
    - name이 없으면 'step' 기본값
    """
    name = _ev_get(ev, "name", None)
    if not isinstance(name, str) or not name.strip():
        return "step"

    # 'planner.start' -> 'planner'
    if name.endswith(".start") or name.endswith(".end"):
        return name.rsplit(".", 1)[0]
    return name


# ----------------------------
# Render meta summary
# ----------------------------
def build_meta_summary(meta: Any) -> str:
    """
    P2-2-C Meta Contract v1 요약을 사용자에게 보여준다.
    meta가 없거나 dict가 아니면 빈 문자열 반환.
    """
    if not isinstance(meta, dict):
        return ""

    agent_id = _meta_get(meta, ["agent_id"], "-")
    mode = _meta_get(meta, ["mode"], "-")
    approved = bool(_meta_get(meta, ["approved"], False))
    file_kind = _meta_get(meta, ["file_kind"], "unknown")
    artifacts_count = _meta_get(meta, ["artifacts_count"], 0)
    error_code = _meta_get(meta, ["error_code"], None)

    trace_id = _meta_get(meta, ["trace_id"], "-")

    llm_used = bool(_meta_get(meta, ["llm", "used"], False))
    llm_status = _meta_get(meta, ["llm", "status"], "-")
    llm_reason = _meta_get(meta, ["llm", "reason"], None)
    llm_model = _meta_get(meta, ["llm", "model"], None)

    review_issues = _meta_get(meta, ["review", "issues"], []) or []
    review_followups = _meta_get(meta, ["review", "followups"], []) or []

    ok_mark = "✅" if approved else "❌"

    lines: List[str] = []
    lines.append("## Meta 요약")
    lines.append(f"- Agent: `{agent_id}` / Mode: `{mode}`")
    lines.append(f"- Approved: {ok_mark}")
    lines.append(f"- File kind: `{file_kind}`")
    lines.append(f"- Artifacts: `{artifacts_count}`")
    lines.append(f"- Trace: `{trace_id}`")

    llm_line = f"- LLM: used={llm_used}, status=`{llm_status}`"
    if llm_reason:
        llm_line += f", reason=`{llm_reason}`"
    if llm_model:
        llm_line += f", model=`{llm_model}`"
    lines.append(llm_line)

    if error_code:
        lines.append(f"- Error code: `{error_code}`")

    if isinstance(review_issues, list) and review_issues:
        lines.append("\n### Reviewer issues")
        for it in review_issues[:5]:
            lines.append(f"- {it}")

    if isinstance(review_followups, list) and review_followups:
        lines.append("\n### Reviewer followups")
        for it in review_followups[:5]:
            lines.append(f"- {it}")

    return "\n".join(lines).strip()


# ----------------------------
# Render events
# ----------------------------
async def render_events(events: List[AgentEvent]) -> None:
    """
    AgentEvent를 Chainlit Step/Message로 최소 렌더링.
    - dict / object 모두 지원
    - type이 없으면 name suffix로 step_start/step_end 추론
    - 과도한 복잡도 방지: step_start/step_end는 Step으로, 나머지는 메시지로 출력
    """
    for ev in events or []:
        ev_type = _infer_event_type(ev)
        ev_name = _ev_get(ev, "name", "")
        ev_message = _ev_get(ev, "message", "")

        # Step start/end는 Step으로
        if ev_type in ("step_start", "step_end"):
            step_name = _infer_step_name(ev)
            async with cl.Step(name=step_name):
                # step 메시지는 본문으로 보여주되, 없으면 name만 표시
                if isinstance(ev_message, str) and ev_message.strip():
                    await cl.Message(content=ev_message).send()
                else:
                    # 메시지가 없으면 name이라도 표시
                    if isinstance(ev_name, str) and ev_name.strip():
                        await cl.Message(content=ev_name).send()
        else:
            # 일반 로그 출력
            if isinstance(ev_message, str) and ev_message.strip():
                prefix = f"[{ev_name}] " if isinstance(ev_name, str) and ev_name.strip() else ""
                await cl.Message(content=f"{prefix}{ev_message}").send()


# ----------------------------
# Artifacts -> Chainlit elements
# ----------------------------
def _to_elements(artifacts: List[ArtifactRef]) -> List[cl.Element]:
    elements: List[cl.Element] = []
    for a in artifacts or []:
        # ArtifactRef가 dataclass/객체일 가능성 대비
        kind = getattr(a, "kind", None) if not isinstance(a, dict) else a.get("kind")
        name = getattr(a, "name", None) if not isinstance(a, dict) else a.get("name")
        path = getattr(a, "path", None) if not isinstance(a, dict) else a.get("path")

        if not name or not path:
            continue

        if kind == "image":
            elements.append(cl.Image(name=name, path=path, display="inline"))
        else:
            elements.append(cl.File(name=name, path=path, display="inline"))
    return elements


# ----------------------------
# Render final result
# ----------------------------
async def render_result(result: AgentResult) -> None:
    """
    최종 출력:
    1) (선택) meta 요약 출력
    2) (선택) events 출력
    3) 최종 text + artifacts elements 출력
    """
    # result가 혹시 dict로 올 가능성까지 방어
    if isinstance(result, dict):
        meta = result.get("meta")
        events = result.get("events") or []
        artifacts = result.get("artifacts") or []
        text = result.get("text") or ""
    else:
        meta = getattr(result, "meta", None)
        events = getattr(result, "events", None) or []
        artifacts = getattr(result, "artifacts", None) or []
        text = getattr(result, "text", "") or ""

    # 1) meta 요약
    summary = build_meta_summary(meta)
    if summary:
        await cl.Message(content=summary).send()

    # 2) 이벤트 렌더
    if events:
        await render_events(events)

    # 3) 산출물 + 최종 메시지
    elements = _to_elements(artifacts)
    await cl.Message(content=text, elements=elements).send()
