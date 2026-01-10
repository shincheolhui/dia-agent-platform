# core/tests/smoke_file_loader.py
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.tools.file_loader import load_file


FIX_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _get_attr(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_data(load_res) -> dict:
    data = _get_attr(load_res, "data", None)
    return data if isinstance(data, dict) else {}


def smoke_file_loader() -> None:
    # 1) CSV
    csv_path = FIX_DIR / "sample_utf8bom.csv"
    assert csv_path.exists(), f"fixture missing: {csv_path}"

    r = load_file(str(csv_path))
    assert bool(_get_attr(r, "ok", False)) is True, f"csv load failed: {_get_attr(r, 'error', None)}"
    kind = str(_get_attr(r, "kind", "") or _get_data(r).get("kind", "")).lower()
    assert kind == "csv", f"csv expected kind=csv but got {kind!r}"

    df = _get_attr(r, "df", None) or _get_attr(r, "dataframe", None) or _get_data(r).get("df")
    assert isinstance(df, pd.DataFrame), f"csv expected df DataFrame but got {type(df).__name__}"

    # 최소 shape 고정(샘플 파일에 맞게 조정 가능)
    assert df.shape[0] > 0 and df.shape[1] > 0, f"csv df shape invalid: {df.shape}"

    # 2) LOG(TEXT)
    log_path = FIX_DIR / "sample.log"
    assert log_path.exists(), f"fixture missing: {log_path}"

    r = load_file(str(log_path))
    assert bool(_get_attr(r, "ok", False)) is True, f"log load failed: {_get_attr(r, 'error', None)}"
    kind = str(_get_attr(r, "kind", "") or _get_data(r).get("kind", "")).lower()
    assert kind == "text", f"log expected kind=text but got {kind!r}"

    data = _get_data(r)
    text = (data.get("text") or data.get("content") or "").strip()
    assert len(text) > 0, "log expected data.text/content not empty"

    # 3) TXT(TEXT)
    txt_path = FIX_DIR / "sample.txt"
    assert txt_path.exists(), f"fixture missing: {txt_path}"

    r = load_file(str(txt_path))
    assert bool(_get_attr(r, "ok", False)) is True, f"txt load failed: {_get_attr(r, 'error', None)}"
    kind = str(_get_attr(r, "kind", "") or _get_data(r).get("kind", "")).lower()
    assert kind == "text", f"txt expected kind=text but got {kind!r}"

    data = _get_data(r)
    text = (data.get("text") or data.get("content") or "").strip()
    assert len(text) > 0, "txt expected data.text/content not empty"

    # 4) PDF (선택)
    pdf_path = FIX_DIR / "sample.pdf"
    if pdf_path.exists():
        r = load_file(str(pdf_path))
        assert bool(_get_attr(r, "ok", False)) is True, f"pdf load failed: {_get_attr(r, 'error', None)}"
        kind = str(_get_attr(r, "kind", "") or _get_data(r).get("kind", "")).lower()
        assert kind == "pdf", f"pdf expected kind=pdf but got {kind!r}"

        data = _get_data(r)
        text = (data.get("text") or data.get("content") or "").strip()
        assert len(text) > 0, "pdf expected extracted text not empty (use a text-based sample.pdf)"
