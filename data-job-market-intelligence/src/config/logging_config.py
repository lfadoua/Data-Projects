"""Call once at an entry point; never log secrets or full user prompts."""

import logging

from src.config.security import configured_secrets, redact_sensitive
from src.config.settings import PROJECT_ROOT


class RedactingFormatter(logging.Formatter):
    """Redact after formatting, including interpolated arguments and tracebacks."""

    def __init__(self, fmt=None, datefmt=None, *, secrets=(), wrapped=None):
        super().__init__(fmt, datefmt)
        self.secrets = secrets
        self.wrapped = wrapped

    def format(self, record):
        formatted = self.wrapped.format(record) if self.wrapped else super().format(record)
        return redact_sensitive(formatted, self.secrets)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    secrets = configured_secrets(PROJECT_ROOT / ".env")
    handlers = {
        handler
        for logger in (logging.getLogger(), logging.getLogger("uvicorn"))
        for handler in logger.handlers
    }
    for handler in handlers:
        formatter = handler.formatter
        if isinstance(formatter, RedactingFormatter):
            formatter.secrets = secrets
            continue
        handler.setFormatter(RedactingFormatter(secrets=secrets, wrapped=formatter))
