"""Logging configuration.

The 500 handler returns a request ID and nothing else, on the promise that an
operator can find the matching trace in the log. That promise is only worth
anything if the ID actually reaches the log line — and the JSON formatter that
carries it is only used outside development, which is exactly where nobody is
watching a terminal.
"""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from app.core.config import get_settings
from app.core.logging import RequestIdFilter, configure_logging, get_logger, request_id_ctx


@pytest.fixture(autouse=True)
def restore_root_logging():
    """Put the root logger back.

    `configure_logging` clears root handlers, which would otherwise take
    pytest's own capture handler with it and leave every later test in the
    session logging into nothing.
    """
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    root.handlers = handlers
    root.setLevel(level)


def emitted(environment: str, message: str = "scoring failed") -> str:
    """Configure logging for an environment and capture one line."""
    settings = get_settings()
    original = settings.ENVIRONMENT
    settings.ENVIRONMENT = environment
    try:
        configure_logging()
        stream = StringIO()
        handler = logging.getLogger().handlers[0]
        handler.setStream(stream)
        get_logger("app.test").error(message)
        handler.flush()
        return stream.getvalue()
    finally:
        settings.ENVIRONMENT = original


class TestRequestIdFilter:
    def test_it_supplies_a_placeholder_outside_a_request(self):
        """Background work still logs, and a formatter with no field raises."""
        request_id_ctx.set(None)
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "hello", None, None)
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "-"

    def test_it_carries_the_current_request_id(self):
        token = request_id_ctx.set("abc-123")
        try:
            record = logging.LogRecord("app", logging.INFO, __file__, 1, "hello", None, None)
            RequestIdFilter().filter(record)
            assert record.request_id == "abc-123"
        finally:
            request_id_ctx.reset(token)


class TestFormatters:
    def test_production_logs_are_json_an_aggregator_can_parse(self):
        token = request_id_ctx.set("trace-me")
        try:
            line = emitted("production")
        finally:
            request_id_ctx.reset(token)

        record = json.loads(line)
        assert record["message"] == "scoring failed"
        assert record["request_id"] == "trace-me"
        assert record["name"] == "app.test"

    def test_the_json_fields_are_named_for_the_aggregator(self):
        """`levelname` and `asctime` are Python's names, not a log platform's."""
        record = json.loads(emitted("staging"))
        assert record["level"] == "ERROR"
        assert record["timestamp"]
        assert "levelname" not in record and "asctime" not in record

    def test_development_logs_are_readable_by_a_person(self):
        token = request_id_ctx.set("trace-me")
        try:
            line = emitted("development")
        finally:
            request_id_ctx.reset(token)

        assert line.startswith("ERROR")
        assert "[trace-me]" in line
        assert "scoring failed" in line


class TestNoiseControl:
    def test_the_chatty_libraries_are_quietened(self):
        """Access logs and SQL echo drown out the application's own lines."""
        emitted("production")
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("passlib").level == logging.ERROR

    def test_sql_echo_follows_its_setting(self):
        settings = get_settings()
        original = settings.DB_ECHO
        settings.DB_ECHO = True
        try:
            emitted("production")
            assert logging.getLogger("sqlalchemy.engine").level == logging.INFO
        finally:
            settings.DB_ECHO = original
