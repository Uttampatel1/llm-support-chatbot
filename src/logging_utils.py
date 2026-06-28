"""Lightweight, dependency-free logging for the project.

Call :func:`configure_logging` once at process start (the entry points do this
for you), then use :func:`get_logger` everywhere else. The log level is read
from the ``LOG_LEVEL`` environment variable (default ``INFO``), so you can run
``LOG_LEVEL=DEBUG python -m src.run_...`` for verbose output.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator, Optional

_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    """Configure root logging once. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, lvl, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    configure_logging()
    return logging.getLogger(name)


@contextmanager
def log_timing(logger: logging.Logger, label: str) -> Iterator[None]:
    """Context manager that logs how long a block took, in milliseconds."""
    start = time.perf_counter()
    logger.info("%s ...", label)
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info("%s done in %.1f ms", label, elapsed_ms)
