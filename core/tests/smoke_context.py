# core/tests/smoke_context.py
from __future__ import annotations

from pathlib import Path

from core.context import normalize_context


def smoke_context() -> None:
    # 1) 최소 입력 (session_id 누락)
    ctx = normalize_context({})
    # ctx는 dataclass/객체일 수 있으므로 attribute로 접근
    sid = getattr(ctx, "session_id", None)
    assert sid is not None and str(sid).strip() != "", f"session_id should be defaulted but got {sid!r}"

    files = getattr(ctx, "uploaded_files", None)
    assert files is not None, "uploaded_files should exist on AgentContext"
    assert isinstance(files, list), f"uploaded_files should be list but got {type(files).__name__}"

    # 2) uploaded_files가 dict 형태로 들어오는 케이스
    raw = {
        "session_id": "S-1",
        "uploaded_files": [{"name": "a.csv", "path": r"tests\fixtures\sample_utf8bom.csv", "mime": "text/csv"}],
    }
    ctx = normalize_context(raw)
    assert getattr(ctx, "session_id") == "S-1"
    files = getattr(ctx, "uploaded_files", [])
    assert len(files) == 1
    f0 = files[0]
    # f0도 dict이거나 객체일 수 있으니 둘 다 허용하며, 최소 필드 존재만 고정
    name = f0.get("name") if isinstance(f0, dict) else getattr(f0, "name", None)
    path = f0.get("path") if isinstance(f0, dict) else getattr(f0, "path", None)
    assert name, "uploaded_files[0].name missing"
    assert path, "uploaded_files[0].path missing"

    # 3) uploaded_files가 객체형으로 들어오는 케이스(Chainlit UploadedFileRef 유사)
    class _FakeUpload:
        def __init__(self, name: str, path: str, mime: str = "text/plain"):
            self.name = name
            self.path = path
            self.mime = mime

    raw = {
        "session_id": "S-2",
        "uploaded_files": [_FakeUpload("a.log", str(Path("tests/fixtures/sample.log")))],
    }
    ctx = normalize_context(raw)
    assert getattr(ctx, "session_id") == "S-2"
    files = getattr(ctx, "uploaded_files", [])
    assert len(files) == 1
