# core/tools/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    last_error: Optional[str] = None
