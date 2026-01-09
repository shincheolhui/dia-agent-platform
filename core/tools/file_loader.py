# core/tools/file_loader.py
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None

from core.tools.base import ToolResult


def _read_tail_text(p: Path, *, max_chars: int = 20000) -> tuple[str, bool]:
    """
    텍스트 파일(.log/.txt/.out)을 tail 방식으로 읽는다.
    반환: (text, truncated)
    """
    data = p.read_text(encoding="utf-8", errors="replace")
    if len(data) <= max_chars:
        return data, False
    return data[-max_chars:], True


def load_file(
    path: str,
    *,
    max_rows: int = 5000,
    pdf_max_pages: int = 1,
    text_max_chars: int = 20000,
) -> ToolResult:
    """
    범용 파일 로더 (Phase2-1 표준 Tool).
    - CSV/XLSX/PDF + TEXT(.log/.txt/.out) 지원
    - 반환은 ToolResult로 통일
    """
    p = Path(path)
    if not p.exists():
        return ToolResult(ok=False, summary="file not found", error="file_not_found", last_error=str(p))

    ext = p.suffix.lower()

    try:
        # 0) TEXT (log/txt/out)
        if ext in {".log", ".txt", ".out"}:
            text, truncated = _read_tail_text(p, max_chars=text_max_chars)
            return ToolResult(
                ok=True,
                summary=f"loaded text: chars={len(text)} truncated={truncated}",
                data={
                    "kind": "text",
                    "path": str(p),
                    "ext": ext,
                    "text": text,
                    "text_truncated": truncated,
                    "text_max_chars": int(text_max_chars),
                },
            )

        # 1) CSV
        if ext == ".csv":
            df_full = pd.read_csv(p)
            truncated = len(df_full) > max_rows
            df = df_full.head(max_rows) if truncated else df_full

            return ToolResult(
                ok=True,
                summary=f"loaded csv: shape={df.shape[0]}x{df.shape[1]} truncated={truncated}",
                data={
                    "kind": "csv",
                    "path": str(p),
                    "columns": [str(c) for c in df.columns.tolist()],
                    "shape": [int(df.shape[0]), int(df.shape[1])],
                    "preview_csv": df.head(10).to_csv(index=False),
                    "max_rows": int(max_rows),
                    "truncated": truncated,
                    "rows_total": int(len(df_full)),
                    # ✅ Agent가 직접 파일을 다시 읽지 않도록 df 제공
                    "df": df,
                },
            )

        # 2) Excel
        if ext in {".xlsx", ".xls"}:
            df_full = pd.read_excel(p)
            truncated = len(df_full) > max_rows
            df = df_full.head(max_rows) if truncated else df_full

            return ToolResult(
                ok=True,
                summary=f"loaded excel: shape={df.shape[0]}x{df.shape[1]} truncated={truncated}",
                data={
                    "kind": "excel",
                    "path": str(p),
                    "columns": [str(c) for c in df.columns.tolist()],
                    "shape": [int(df.shape[0]), int(df.shape[1])],
                    "preview_csv": df.head(10).to_csv(index=False),
                    "max_rows": int(max_rows),
                    "truncated": truncated,
                    "rows_total": int(len(df_full)),
                    # ✅ Agent가 직접 파일을 다시 읽지 않도록 df 제공
                    "df": df,
                },
            )

        # 3) PDF
        if ext == ".pdf":
            if pdfplumber is None:
                return ToolResult(
                    ok=False,
                    summary="pdfplumber not installed",
                    error="missing_dependency",
                    last_error="pdfplumber",
                )

            texts = []
            with pdfplumber.open(p) as pdf:
                for page in pdf.pages[: max(1, pdf_max_pages)]:
                    text = (page.extract_text() or "").strip()
                    texts.append(text)

            joined = "\n\n".join([t for t in texts if t])
            if not joined:
                joined = "(텍스트 추출 실패: 스캔 PDF 가능)"

            return ToolResult(
                ok=True,
                summary=f"loaded pdf: pages={min(pdf_max_pages, len(texts))}",
                data={
                    "kind": "pdf",
                    "path": str(p),
                    "pages_read": int(min(pdf_max_pages, len(texts))),
                    "text": joined,
                    "pdf_max_pages": int(pdf_max_pages),
                },
            )

        return ToolResult(ok=False, summary="unsupported file type", error="unsupported_type", last_error=ext)

    except Exception as e:
        return ToolResult(
            ok=False,
            summary="file load failed",
            error="load_failed",
            last_error=f"{type(e).__name__}: {e}",
        )
