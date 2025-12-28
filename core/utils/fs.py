from __future__ import annotations

import os
import shutil
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def copy_to(src_path: str | Path, dst_dir: str | Path, dst_name: str) -> Path:
    dst_dir_p = ensure_dir(dst_dir)
    dst_path = dst_dir_p / dst_name
    shutil.copy2(str(src_path), str(dst_path))
    return dst_path


def safe_filename(name: str) -> str:
    # Windows/Unix 공통으로 위험한 문자 제거
    bad = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for b in bad:
        name = name.replace(b, "_")
    return name.strip() or "file"
