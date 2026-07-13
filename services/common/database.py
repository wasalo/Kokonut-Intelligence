"""Small psycopg2 adapter for services using a SQLAlchemy-like execute API.

This keeps credit-domain SQL readable with named ``:parameter`` placeholders
without adding SQLAlchemy as a runtime dependency.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Iterator, Optional

import psycopg2.extras

from services.ingestion.base import get_db

_NAMED_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


def _to_psycopg2_sql(sql: str) -> str:
    """Translate ``:name`` parameters while preserving PostgreSQL ``::`` casts."""
    return _NAMED_PARAMETER.sub(r"%(\1)s", sql)


class MappingResult:
    """Eager result wrapper exposing the subset used by credit services."""

    def __init__(self, rows: list[dict[str, Any]], rowcount: int):
        self._rows = rows
        self.rowcount = rowcount

    def mappings(self) -> "MappingResult":
        return self

    def first(self) -> Optional[dict[str, Any]]:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._rows)


class DatabaseConnection:
    """Transaction-owning connection adapter used by CLI entry points."""

    def __init__(self, connection=None):
        self._connection = connection or get_db()

    @staticmethod
    def text(sql: str) -> str:
        return sql

    def execute(self, sql: str, params: Optional[dict[str, Any]] = None) -> MappingResult:
        cur = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(_to_psycopg2_sql(sql), params or {})
            rows = [dict(row) for row in cur.fetchall()] if cur.description else []
            return MappingResult(rows, cur.rowcount)
        finally:
            cur.close()

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def get_connection() -> DatabaseConnection:
    """Return a transaction-owning credit-service connection."""
    return DatabaseConnection()
