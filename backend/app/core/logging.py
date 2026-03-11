"""
logging.py — Structured JSON logging configuration.

In production (DEBUG=False), every log line is a JSON object so Railway's
log drain can filter, alert, and aggregate by field:

  {"ts": "2025-01-01T12:00:00Z", "level": "INFO", "logger": "app.ingestion.pipeline",
   "msg": "Ingestion complete", "session_id": "abc123", "records": 412}

In development (DEBUG=True), logs are human-readable coloured text.

Usage in any module:
    from app.core.logging import get_logger
    logger = get_logger(__name__)

    logger.info("Ingestion complete", session_id=session_id, records=412)

The structlog.contextvars module lets you bind request-scoped fields
(outlet_id, session_id) once at the start of a request and they appear
on every log line within that request automatically.
"""
import logging
import logging.config
import sys
from typing import Any

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """
    Configure structlog + stdlib logging. Call once at startup in main.py.
    All existing `logging.getLogger(__name__)` calls continue to work
    because structlog wraps the stdlib logger transparently.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,          # request-scoped fields
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    if settings.DEBUG:
        # Human-readable coloured output for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSON lines for Railway log drain
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors          = shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class       = structlog.stdlib.BoundLogger,
        context_class       = dict,
        logger_factory      = structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use = True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain = shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "arq.worker"):
        logging.getLogger(noisy).setLevel(
            logging.DEBUG if settings.DEBUG else logging.WARNING
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Drop-in replacement for logging.getLogger(). Returns a structlog logger
    that accepts keyword arguments for structured context.

    Example:
        logger = get_logger(__name__)
        logger.info("session started", session_id=sid, outlet_id=oid)
    """
    return structlog.get_logger(name)


# ── Request context binding ───────────────────────────────────────────────────
# Call these at the start/end of each request to bind outlet_id automatically
# to every log line within that request (works with structlog.contextvars).

def bind_request_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current async context (request-scoped)."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    """Clear context at end of request."""
    structlog.contextvars.clear_contextvars()
