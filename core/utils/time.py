from __future__ import annotations

from datetime import datetime


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
