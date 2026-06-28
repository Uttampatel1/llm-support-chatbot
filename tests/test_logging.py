from __future__ import annotations

import logging

from src.logging_utils import configure_logging, get_logger, log_timing


def test_get_logger_returns_logger():
    log = get_logger("test.module")
    assert isinstance(log, logging.Logger)
    assert log.name == "test.module"


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging("DEBUG")  # second call is a no-op, must not raise


def test_log_timing_emits_start_and_done(caplog):
    log = get_logger("test.timing")
    with caplog.at_level(logging.INFO, logger="test.timing"):
        with log_timing(log, "unit-of-work"):
            pass
    messages = [r.getMessage() for r in caplog.records]
    assert any("unit-of-work ..." in m for m in messages)
    assert any("done in" in m for m in messages)
