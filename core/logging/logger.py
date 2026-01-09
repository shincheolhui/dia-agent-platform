# core/logging/logger.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_DEFAULT_FMT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "trace_id=%(trace_id)s | %(message)s"
)

# 전역 trace_id 보관 (LogRecordFactory가 참조)
_TRACE_ID: str = "-"


def set_trace_id(trace_id: str | None) -> None:
    """
    런타임에 trace_id를 갱신한다.
    (예: chainlit session_id, request_id 등)
    """
    global _TRACE_ID
    _TRACE_ID = (trace_id or "-")


def _install_trace_id_record_factory() -> None:
    """
    모든 LogRecord에 trace_id 필드를 '항상' 주입한다.
    Formatter가 %(trace_id)s 를 요구해도 KeyError가 절대 나지 않는다.

    - 로거/핸들러/서드파티(engineio/chainlit/openai 등) 출처와 무관하게 적용됨
    """
    if getattr(logging, "_dia_record_factory_installed", False):
        return

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        # record에 trace_id가 아예 없거나 None이면 무조건 기본값 주입
        if not hasattr(record, "trace_id") or record.trace_id is None:
            record.trace_id = _TRACE_ID
        return record

    logging.setLogRecordFactory(record_factory)
    logging._dia_record_factory_installed = True  # type: ignore[attr-defined]


class TraceIdFilter(logging.Filter):
    """
    (보조 안전장치)
    핸들러/로거 레벨에서 trace_id가 누락된 레코드가 있어도 기본값을 넣는다.
    LogRecordFactory가 1차로 막지만, 혹시 모를 경로를 위한 2차 방어.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id") or record.trace_id is None:
            record.trace_id = _TRACE_ID
        return True


def setup_logging(
    *,
    workspace_dir: str = "workspace",
    log_filename: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    enable_console: bool = False,  # ✅ 옵션 A: 기본은 콘솔 핸들러를 설치하지 않음
) -> TraceIdFilter:
    """
    옵션 A(권장) 구성:
    - trace_id RecordFactory 설치(전역 주입)
    - 루트 로거에 RotatingFileHandler만 구성 (enable_console=False 기본)
    - 중복 핸들러 방지
    - TraceIdFilter 반환(호환 목적)
    """
    _install_trace_id_record_factory()

    log_dir = Path(workspace_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename

    root = logging.getLogger()
    root.setLevel(level)

    # 이미 구성되었으면 필터만 반환
    if getattr(root, "_dia_logging_configured", False):
        for f in getattr(root, "_dia_filters", []):
            if isinstance(f, TraceIdFilter):
                return f
        tf = TraceIdFilter()
        root.addFilter(tf)
        root._dia_filters = [tf]  # type: ignore[attr-defined]
        return tf

    formatter = logging.Formatter(_DEFAULT_FMT)

    # ✅ Filter (2차 방어)
    tf = TraceIdFilter()
    root.addFilter(tf)

    # ✅ File handler (rotating) - 항상 설치
    fh = RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    # 핸들러에도 필터 적용(서드파티 로그 포함 시 방어 강화)
    fh.addFilter(tf)
    root.addHandler(fh)

    # ✅ Console handler는 옵션 (기본 False)
    if enable_console:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(formatter)
        sh.addFilter(tf)
        root.addHandler(sh)

    # 플래그 저장
    root._dia_logging_configured = True  # type: ignore[attr-defined]
    root._dia_filters = [tf]  # type: ignore[attr-defined]

    return tf


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
