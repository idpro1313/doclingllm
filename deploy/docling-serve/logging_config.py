"""
Logging configuration for docling-serve (doclingllm overlay).

Based on upstream docling_serve.logging_config with quieter poll noise:
- httpx / httpcore at WARNING (Gradio status poll spam)
- uvicorn.access filter for /v1/status/poll and /health
"""

import contextvars
import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)

_QUIET_ACCESS_SUBSTRINGS = (
    "/v1/status/poll/",
    "/health",
)


class QuietAccessFilter(logging.Filter):
    """Drop high-frequency health/poll access lines from uvicorn.access."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(fragment in message for fragment in _QUIET_ACCESS_SUBSTRINGS)


class ColoredLogFormatter(logging.Formatter):
    """Colored formatter for text log output."""

    COLOR_CODES = {
        logging.DEBUG: "\033[94m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[95m",
    }
    RESET_CODE = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLOR_CODES.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{self.RESET_CODE}"
        return super().format(record)


def get_log_context() -> dict[str, Any]:
    """Get the current log context."""
    return _log_context.get()


def set_log_context(context: dict[str, Any]) -> None:
    """Set the log context."""
    _log_context.set(context)


def clear_log_context() -> None:
    """Clear the log context."""
    _log_context.set({})


class JSONLogFormatter(logging.Formatter):
    """JSON log formatter that includes context data from request headers."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)

        context = get_log_context()
        if context:
            log_entry.update(context)

        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            s = time.strftime("%Y-%m-%dT%H:%M:%S", ct)
            s = f"{s}.{int(record.msecs):03d}Z"
        return s


class LogContextMiddleware(BaseHTTPMiddleware):
    """Extract X-Docling-Log-* headers into log context for the request."""

    def __init__(self, app, header_prefix: str = "X-Docling-Log-"):
        super().__init__(app)
        self.header_prefix = header_prefix.lower()

    async def dispatch(self, request: Request, call_next) -> Response:
        context: dict[str, Any] = {}

        for header_name, header_value in request.headers.items():
            if header_name.lower().startswith(self.header_prefix):
                field_name = header_name[len(self.header_prefix) :]
                context[field_name] = header_value

        set_log_context(context)
        return await call_next(request)


def setup_logging(
    log_format: str = "text",
    log_level: str = "INFO",
    header_prefix: str = "X-Docling-Log-",
) -> None:
    """Configure application logging; quiet Gradio poll / health access noise."""
    # BUG_FIX_CONTEXT: Gradio UI polls /v1/status/poll every ~5s via httpx; at INFO
    # this doubles with uvicorn.access and drowns useful pipeline logs.
    root_logger = logging.getLogger()

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()

    formatter: logging.Formatter
    if log_format.lower() == "json":
        formatter = JSONLogFormatter()
    else:
        formatter = ColoredLogFormatter(
            "%(levelname)s:\t%(asctime)s - %(name)s - %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    access_filter = QuietAccessFilter()
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, log_level.upper()))
        logger.propagate = False
        if logger_name == "uvicorn.access":
            logger.addFilter(access_filter)

    for quiet_name in ("httpx", "httpcore"):
        quiet_logger = logging.getLogger(quiet_name)
        quiet_logger.setLevel(logging.WARNING)
        quiet_logger.propagate = True
