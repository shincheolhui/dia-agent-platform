# core/tests/smoke_audit.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from core.agent.audit import export_and_append
from core.artifacts.types import ArtifactRef, AgentResult


@dataclass
class _Settings:
    WORKSPACE_DIR: str = "workspace"
    AUDIT_ENABLED: bool = True
    AUDIT_STORE_MESSAGE: bool = False
    AUDIT_MESSAGE_MAX_LEN: int = 200
    AUDIT_STORE_FILE_PATH: bool = True


def smoke_audit() -> None:
    settings = _Settings()

    # 최소 AgentResult 더미
    result = AgentResult(
        text="ok",
        artifacts=[ArtifactRef(kind="markdown", name="x.md", path="workspace/artifacts/x.md", mime_type="text/markdown")],
        events=[],
        meta={
            "agent_id": "dia",
            "mode": "p2-2-d",
            "approved": True,
            "file_kind": "csv",
            "artifacts_count": 1,
            "error_code": None,
            "llm": {"used": False, "status": "skipped", "reason": "llm_disabled", "model": None},
            "review": {"issues": [], "followups": []},
            "trace_id": "test-trace",
        },
    )

    # context 더미
    context: Dict[str, Any] = {
        "session_id": "test-trace",
        "uploaded_files": [{"name": "a.csv", "path": "workspace/uploads/a.csv", "mime": "text/csv"}],
    }

    json_path, jsonl_path, entry = export_and_append(
        result=result,
        user_message="요약해줘",
        context=context,
        settings=settings,
    )

    assert entry is not None
    assert json_path is not None and json_path.exists()
    assert jsonl_path is not None and jsonl_path.exists()

    # json 파싱 가능해야 함
    loaded = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert loaded.get("schema_version") == "audit.v1"
    assert loaded.get("meta", {}).get("agent_id") == "dia"

    # jsonl 마지막 라인이 JSON이어야 함
    lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    _ = json.loads(lines[-1])
