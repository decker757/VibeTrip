"""Postgres connection helper shared by the repositories.

A failed connection starts a cool-down instead of disabling Postgres for the
process lifetime, so a database that comes back is picked up again. While the
connector returns None, callers fall back to in-memory storage.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _psycopg_connect(url: str, connect_timeout: int):
    import psycopg

    return psycopg.connect(url, connect_timeout=connect_timeout)


class PostgresConnector:
    def __init__(self, cooldown_seconds: float = 30.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._retry_at: float | None = None
        self._schema_ready = False

    def connect(self) -> Any | None:
        url = os.getenv("DATABASE_URL") or None
        if not url:
            return None
        if self._retry_at is not None and self._clock() < self._retry_at:
            return None
        try:
            connection = _psycopg_connect(url, connect_timeout=2)
        except ImportError:
            return None
        except Exception as error:
            self.mark_failed(error)
            return None
        try:
            if not self._schema_ready:
                self._ensure_schema(connection)
                self._schema_ready = True
        except Exception as error:
            connection.close()
            self.mark_failed(error)
            return None
        self._retry_at = None
        return connection

    def mark_failed(self, error: Exception) -> None:
        self._retry_at = self._clock() + self._cooldown_seconds
        logger.warning("Postgres unavailable, using in-memory storage for %.0fs: %s", self._cooldown_seconds, error)

    @staticmethod
    def _ensure_schema(connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_PATH.read_text())
        connection.commit()
