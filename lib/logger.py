import datetime
import logging
from typing import Any, Dict, Optional

import graypy

from config import GRAYLOG_HOST, GRAYLOG_PORT, MACHINE_TOKEN, UNIQUE_ID

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
        # Always add/update timestamp to UTC isoformat
        record.timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        return True


class Logger(logging.Logger):
    """
    Custom Logger implementation with Graylog support and automatic context injection.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.setLevel(logging.DEBUG)

        # Add context filter
        self.addFilter(ContextFilter())

        # Setup Graylog handler if host is provided
        if GRAYLOG_HOST:
            handler = graypy.GELFUDPHandler(
                GRAYLOG_HOST,
                GRAYLOG_PORT,
                extra_fields=True,
                debugging_fields=False
            )
            self.addHandler(handler)

        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
        console_handler.setFormatter(formatter)
        self.addHandler(console_handler)
