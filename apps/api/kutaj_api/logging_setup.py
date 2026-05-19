import logging
import sys

import structlog

from .settings import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    shared: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if settings.is_prod:
        processors = [
            *shared,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [*shared, structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)
    # Uvicorn access log šumí v dev; v prod ho rieši nginx access log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
