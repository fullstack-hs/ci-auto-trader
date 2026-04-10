import datetime
import json
import logging
import os
from typing import Any, Dict, Optional

import graypy

from config import GRAYLOG_HOST, GRAYLOG_PORT, MACHINE_TOKEN, UNIQUE_ID

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Constants for default values
DEFAULT_CTX = "auto_trader"


class ContextFilter(logging.Filter):
    """
    Logging filter to inject context information into every log record.
    """

    def __init__(self):
        super().__init__()

    def filter(self, record: logging.LogRecord) -> bool:
        record.ctx = DEFAULT_CTX
        record.machine_token = MACHINE_TOKEN
        record.user_id = UNIQUE_ID
        record.timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        standard_keys = {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                        'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                        'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                        'processName', 'process', 'ctx', 'machine_token', 'user_id', 'timestamp'}
        record.extra = {k: v for k, v in record.__dict__.items() if k not in standard_keys}
        return True


def _format_extra(extra: Dict[str, Any], indent: int = 0) -> str:
    """Format extra dict in a readable way with proper nesting."""
    if not extra:
        return ""
    parts = []
    prefix = "  " * indent
    for key, value in extra.items():
        if isinstance(value, dict):
            parts.append(f"{prefix}{key}:")
            parts.append(_format_extra(value, indent + 1))
        elif isinstance(value, list):
            parts.append(f"{prefix}{key}: [")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    parts.append(f"{prefix}  [{i}]:")
                    parts.append(_format_extra(item, indent + 2))
                else:
                    parts.append(f"{prefix}  [{i}]: {item}")
            parts.append(f"{prefix}]")
        else:
            parts.append(f"{prefix}{key}: {value}")
    return "\n".join(parts) if indent > 0 else "\n" + "\n".join(parts)


class ReadableFormatter(logging.Formatter):
    """Formatter that outputs extra fields in a readable tree format."""

    def format(self, record: logging.LogRecord) -> str:
        extra = getattr(record, 'extra', None)
        if extra and isinstance(extra, dict) and extra:
            record.msg = f"{record.msg}\n{_format_extra(extra)}"
        return super().format(record)


class Logger(logging.Logger):
    """
    Custom Logger implementation with Graylog support and automatic context injection.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.setLevel(logging.DEBUG)

        self.addFilter(ContextFilter())

        log_file = os.path.join(LOGS_DIR, "auto_trader.log")
        err_file = os.path.join(LOGS_DIR, "ERR.log")

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = ReadableFormatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s [%(ctx)s] [%(machine_token)s] [%(user_id)s]'
        )
        file_handler.setFormatter(file_formatter)
        self.addHandler(file_handler)

        err_handler = logging.FileHandler(err_file, encoding="utf-8")
        err_handler.setLevel(logging.ERROR)
        err_handler.addFilter(lambda record: record.levelno >= logging.ERROR)
        err_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s]\n%(message)s\n[%(ctx)s] [%(machine_token)s] [%(user_id)s]'
        )
        err_handler.setFormatter(err_formatter)
        self.addHandler(err_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.addHandler(console_handler)

        if GRAYLOG_HOST:
            gray_handler = graypy.GELFUDPHandler(
                GRAYLOG_HOST,
                GRAYLOG_PORT,
                extra_fields=True,
                debugging_fields=False
            )
            self.addHandler(gray_handler)
