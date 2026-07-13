"""structlog configuration: JSON logs with per-request context (request_id).

Every log line is a single JSON object, so the full request lifecycle can be
traced by filtering on `request_id`. Message contents and API keys are never logged.
"""

import logging

import structlog


def configure_logging(log_level: str) -> None:
    """Configure structlog to emit JSON lines at the given level."""
    level: int = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
