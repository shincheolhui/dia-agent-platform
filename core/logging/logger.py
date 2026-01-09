# core/logging/logger.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_DEFAULT_FMT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "trace_id=%(trace_id)s | %(message)s"
)

class TraceIdFilter(logging.Filter):
    """
    모든 LogRecord에 trace_id가 없으면 기본값을 주입한다.
    또한 set_trace_id()로 런타임에 trace_id를 갱신할 수 있다.
    """
    def __init__(self, trace_id: str = "-"):
        super().__init__()
        self._trace_id = trace_id

    def set_trace_id(self, trace_id: str | None):
        self._trace_id = (trace_id or "-")

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = self._trace_id
        # 혹시 None이면 안전 처리
        if record.trace_id is None:
            record.trace_id = "-"
        return True


def setup_logging(
    *,
    workspace_dir: str = "workspace",
    log_filename: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> TraceIdFilter:
    """
    - 루트 로거에 File/Console 핸들러를 달고
    - 모든 핸들러에 TraceIdFilter를 적용하여 trace_id 누락을 방지한다.
    - TraceIdFilter 인스턴스를 반환하여 app 레이어에서 set_trace_id() 가능하게 한다.
    """
    log_dir = Path(workspace_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename

    root = logging.getLogger()
    root.setLevel(level)

    # 중복 핸들러 방지
    if getattr(root, "_dia_logging_configured", False):
        # 이미 설정되어 있다면 trace filter만 찾아서 반환
        for f in getattr(root, "_dia_filters", []):
            if isinstance(f, TraceIdFilter):
                return f
        tf = TraceIdFilter("-")
        root.addFilter(tf)
        root._dia_filters = [tf]
        return tf

    formatter = logging.Formatter(_DEFAULT_FMT)

    # Console
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(formatter)

    # File (rotating)
    fh = RotatingFileHandler(str(log_path), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)

    tf = TraceIdFilter("-")
    root.addFilter(tf)

    root.addHandler(sh)
    root.addHandler(fh)

    root._dia_logging_configured = True
    root._dia_filters = [tf]
    return tf


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
