"""Bounded local redaction for diagnostics; never prints configured credentials."""

import os
import re
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values

SECRET_KEYS = {
    "DATABASE_URL",
    "DB_PASSWORD",
    "POSTGRES_PASSWORD",
    "OPENAI_API_KEY",
    "ADMIN_TOKEN",
}
_DATABASE_URI = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s\"'<>]+", re.I)
_BEARER = re.compile(r"(\bbearer\s+)[A-Za-z0-9._~+/=-]+", re.I)


def configured_secrets(env_file: Path) -> tuple[str, ...]:
    # Include both sources: an overridden file value could remain in an older log.
    file_values = dotenv_values(env_file, interpolate=False)
    values = {
        value
        for source in (file_values, os.environ)
        for key in SECRET_KEYS
        if (value := source.get(key))
    }
    values.update(quote(value, safe="") for value in tuple(values))
    return tuple(sorted(values, key=len, reverse=True))


def redact_sensitive(value: str, secrets=()) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = _DATABASE_URI.sub("[REDACTED_DATABASE_URI]", value)
    return _BEARER.sub(r"\1[REDACTED]", value)
