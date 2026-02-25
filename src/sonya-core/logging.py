"""
로깅 설정 유틸
- setup_logging()으로 sonya_core 전체 로거 설정
- JSON 포맷 옵션 (구조화 로깅)
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Literal

SONYA_LOGGER_NAME = "sonya_core"

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JSONFormatter(logging.Formatter):
    """JSON 구조화 로그 포매터"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, DEFAULT_DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    level: int | str = logging.INFO,
    format: Literal["text", "json"] = "text",
    stream: object = None,
) -> logging.Logger:
    """
    sonya_core 루트 로거를 설정한다.

    Args:
        level: 로그 레벨 (예: logging.DEBUG, "DEBUG")
        format: 로그 포맷 ("text" 또는 "json")
        stream: 출력 스트림 (기본: sys.stderr)

    Returns:
        설정된 sonya_core 루트 로거
    """
    logger = logging.getLogger(SONYA_LOGGER_NAME)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)

    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()

    handler = logging.StreamHandler(stream or sys.stderr)

    if format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )

    logger.addHandler(handler)
    return logger
