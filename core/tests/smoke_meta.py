# core/tests/smoke_meta.py
from __future__ import annotations

from core.agent.stages import build_agent_meta


def smoke_meta() -> None:
    """
    P2-2-C Meta Contract v1의 최소 불변 조건을 검증한다.
    (UI/로깅/외부 소비자가 기대하는 키가 항상 존재해야 함)
    """
    meta = build_agent_meta(
        agent_id="dia",
        mode="p2-2-c",
        file_kind="csv",
        llm_used=False,
        artifacts_count=1,
        approved=True,
        error_code=None,
        extra={"trace_id": "T-1", "review_issues": [], "review_followups": []},
    )

    assert isinstance(meta, dict), "meta must be dict"

    # v1 top-level keys
    for k in ["agent_id", "mode", "approved", "file_kind", "artifacts_count", "llm", "review", "trace_id"]:
        assert k in meta, f"missing meta key: {k}"

    # llm block
    assert isinstance(meta["llm"], dict), "meta.llm must be dict"
    for k in ["used", "status", "reason", "model"]:
        assert k in meta["llm"], f"missing meta.llm key: {k}"

    # review block
    assert isinstance(meta["review"], dict), "meta.review must be dict"
    for k in ["issues", "followups"]:
        assert k in meta["review"], f"missing meta.review key: {k}"

    # 타입 최소 검증
    assert isinstance(meta["review"]["issues"], list), "meta.review.issues must be list"
    assert isinstance(meta["review"]["followups"], list), "meta.review.followups must be list"
