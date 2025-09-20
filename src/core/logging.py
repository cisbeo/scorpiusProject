"""Logging configuration for the application."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.contextvars import merge_contextvars


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
    """
    # Configure structlog processors
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        merge_contextvars,
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
            ],
        )
    )

    # Add file handler if specified
    handlers = [handler]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=shared_processors,
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=getattr(logging, log_level.upper()),
    )

    # Suppress noisy loggers
    for logger_name in ["uvicorn.access", "watchfiles"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self.tokens: list = []

    def __enter__(self) -> None:
        for key, value in self.context.items():
            self.tokens.append(structlog.contextvars.bind_contextvars(**{key: value}))

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        for token in self.tokens:
            structlog.contextvars.unbind_contextvars()


def log_request(request_id: str, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a standardized request log entry.

    Args:
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        **kwargs: Additional log fields

    Returns:
        Log entry dictionary
    """
    return {
        "event": "request",
        "request_id": request_id,
        "method": method,
        "path": path,
        **kwargs,
    }


def log_response(
    request_id: str, status_code: int, duration_ms: float, **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a standardized response log entry.

    Args:
        request_id: Unique request identifier
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        **kwargs: Additional log fields

    Returns:
        Log entry dictionary
    """
    return {
        "event": "response",
        "request_id": request_id,
        "status_code": status_code,
        "duration_ms": duration_ms,
        **kwargs,
    }


def log_error(
    request_id: str, error: Exception, context: str, **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a standardized error log entry.

    Args:
        request_id: Unique request identifier
        error: Exception instance
        context: Error context description
        **kwargs: Additional log fields

    Returns:
        Log entry dictionary
    """
    return {
        "event": "error",
        "request_id": request_id,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        **kwargs,
    }