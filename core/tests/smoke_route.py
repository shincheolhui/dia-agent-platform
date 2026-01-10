# core/tests/smoke_route.py
from __future__ import annotations

from core.agent.router import decide_agent_id
from core.context import normalize_context


def smoke_route() -> None:
    available = ["dia", "logcop"]

    # 1) csv -> dia
    ctx = normalize_context(
        {
            "session_id": "S-ROUTE-1",
            "uploaded_files": [{"name": "x.csv", "path": "tests/fixtures/sample_utf8bom.csv", "mime": "text/csv"}],
        }
    )
    d = decide_agent_id(
        user_message="요약해줘",
        context=ctx,
        available_agent_ids=available,
        default_agent_id="dia",
    )
    assert d.agent_id == "dia", f"expected dia for csv but got {d.agent_id} (reason={d.reason})"

    # 2) log -> logcop
    ctx = normalize_context(
        {
            "session_id": "S-ROUTE-2",
            "uploaded_files": [{"name": "x.log", "path": "tests/fixtures/sample.log", "mime": "text/plain"}],
        }
    )
    d = decide_agent_id(
        user_message="분석해줘",
        context=ctx,
        available_agent_ids=available,
        default_agent_id="dia",
    )
    assert d.agent_id == "logcop", f"expected logcop for log but got {d.agent_id} (reason={d.reason})"

    # 3) 파일 없음 -> default dia (정책 고정)
    ctx = normalize_context({"session_id": "S-ROUTE-3", "uploaded_files": []})
    d = decide_agent_id(
        user_message="뭐 할 수 있어?",
        context=ctx,
        available_agent_ids=available,
        default_agent_id="dia",
    )
    assert d.agent_id == "dia", f"expected default dia when no file but got {d.agent_id} (reason={d.reason})"
