"""Synthetic credentials only; no local .env or external database is read."""

import logging
import sys
from urllib.parse import quote

import pytest
from pydantic import SecretStr, ValidationError

from src.config import settings
from src.config.logging_config import RedactingFormatter
from src.config.security import configured_secrets, redact_sensitive
from src.database import connection


def test_loading_is_literal_and_process_environment_has_precedence(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "DB_PASSWORD='dummy-${DO_NOT_EXPAND}-password'\nDB_NAME=file_example\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("DO_NOT_EXPAND", "unwanted-expansion")
    monkeypatch.setenv("DB_NAME", "process_example")
    settings.get_settings.cache_clear()
    try:
        loaded = settings.get_settings()
        assert loaded.db_password.get_secret_value() == "dummy-${DO_NOT_EXPAND}-password"
        assert loaded.db_name == "process_example"
        assert "dummy-${DO_NOT_EXPAND}-password" not in repr(loaded)
    finally:
        settings.get_settings.cache_clear()


def test_settings_validation_does_not_print_invalid_secret_input():
    invalid = "dummy-private-value-not-a-port"
    with pytest.raises(ValidationError) as caught:
        settings.Settings(db_port=invalid, db_password=SecretStr(invalid))
    assert invalid not in str(caught.value)
    assert "input_value" not in str(caught.value)


def test_redaction_covers_file_and_environment_overrides_and_encoded_values(monkeypatch, tmp_path):
    old, new = "dummy-old-credential@$", "dummy-new-credential@$"
    path = tmp_path / ".env"
    path.write_text(f"DB_PASSWORD='{old}'\n", encoding="utf-8")
    monkeypatch.setenv("DB_PASSWORD", new)
    secrets = configured_secrets(path)
    cleaned = redact_sensitive(" ".join([old, new, quote(old, safe="")]), secrets)
    assert all(value not in cleaned for value in [old, new, quote(old, safe="")])


def test_unknown_database_uri_and_bearer_are_masked_without_configuration():
    cleaned = redact_sensitive(
        "driver postgresql+psycopg://example:dummy-value@example.invalid/db "
        "Authorization: Bearer dummy-token"
    )
    assert "dummy-value" not in cleaned and "dummy-token" not in cleaned
    assert "[REDACTED_DATABASE_URI]" in cleaned


def test_log_formatter_masks_arguments_and_exception_traceback():
    secret = "synthetic-sensitive-value"
    try:
        raise RuntimeError("failed: " + secret)
    except RuntimeError:
        record = logging.LogRecord(
            "synthetic", logging.ERROR, __file__, 1, "%s", (secret,), sys.exc_info()
        )
    formatted = RedactingFormatter("%(message)s", secrets=(secret,)).format(record)
    assert secret not in formatted
    assert "RuntimeError" in formatted and "[REDACTED]" in formatted


def test_engine_hides_bound_parameters_without_connecting(monkeypatch):
    monkeypatch.setattr(
        connection, "get_settings", lambda: settings.Settings(database_url="sqlite://")
    )
    connection.get_engine.cache_clear()
    engine = connection.get_engine()
    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()
        connection.get_engine.cache_clear()


def test_redacting_preserves_specialized_server_formatter():
    from uvicorn.logging import DefaultFormatter

    original = DefaultFormatter("%(levelprefix)s %(message)s", use_colors=False)
    record = logging.LogRecord("uvicorn", logging.ERROR, __file__, 1, "dummy-secret", (), None)
    formatted = RedactingFormatter(wrapped=original, secrets=("dummy-secret",)).format(record)
    assert "ERROR:" in formatted
    assert "dummy-secret" not in formatted
