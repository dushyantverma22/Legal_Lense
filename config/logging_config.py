# config/logging_config.py
import logging
import sys
import structlog
from config.settings import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Configure structlog for structured JSON output.
    
    CONCEPT: structlog wraps Python's standard logging and adds:
    - Automatic JSON serialisation of every log call
    - Context binding — attach request_id once, it appears in ALL
      subsequent log calls within that request without passing it around
    - Processor chain — each log event passes through a pipeline of
      functions that enrich, filter, or format it before output
    
    Call this ONCE at app startup in lifespan(). After that, every
    module just does:
        log = structlog.get_logger()
        log.info("event_name", key=value, key2=value2)
    """
    log_level = logging.DEBUG if settings.openai_api_key else logging.INFO

    # Standard library logging (captures uvicorn, langchain, etc.)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # structlog processor chain
    structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),   # ✅ FIXED
    cache_logger_on_first_use=True,
)