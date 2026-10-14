"""Shared database utilities for Kokonut Intelligence services.

Provides two connection factories:

- ``get_db()`` — returns a raw psycopg2 connection.  This is the canonical
  connection factory used by the vast majority of services (analytics,
  ingestion, systems, threatcasting, etc.).  All import paths
  (``ingestion.base.get_db``, ``common.env.get_db``) delegate here.

- ``get_connection()`` / ``DatabaseConnection`` — a context-managed wrapper
  with SQLAlchemy-like ``:param`` style and auto-commit/rollback.  Used by
  the credit/capital domain and CLI entry points.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras

from .db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

_NAMED_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


def _to_psycopg2_sql(sql: str) -> str:
    """Translate ``:name`` parameters while preserving PostgreSQL ``::`` casts."""
    return _NAMED_PARAMETER.sub(r"%(\1)s", sql)


def get_db(*, connect_timeout: int | None = None):
    """Return a raw psycopg2 connection using shared ``common.db`` constants.

    This is the single canonical connection factory for the platform.
    All other ``get_db`` functions (``ingestion.base``, ``common.env``)
    delegate here to ensure a consistent default database name and
    connection parameters.
    """
    options = {}
    if connect_timeout is not None:
        if isinstance(connect_timeout, bool) or not isinstance(connect_timeout, int) or connect_timeout <= 0:
            raise ValueError("connect_timeout must be a positive integer")
        options["connect_timeout"] = connect_timeout
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        **options,
    )


def _cursor_for(conn):
    """Return a RealDictCursor from a raw psycopg2 connection."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def query(conn, sql: str, params=None):
    """Run *sql* and return all rows as a list of dicts.

    Accepts either a raw psycopg2 connection (from :func:`get_db`) or a
    :class:`DatabaseConnection` (from :func:`get_connection`), so both
    worlds converge on one query helper. This replaces the pervasive
    ``conn.cursor(cursor_factory=RealDictCursor)`` +
    ``[dict(r) for r in cur.fetchall()]`` boilerplate.
    """
    if isinstance(conn, DatabaseConnection):
        return conn.execute(sql, params or {}).all()
    cur = _cursor_for(conn)
    try:
        cur.execute(sql, params or ())
        # Mocks in tests may not expose ``description``; still honor fetchall().
        if getattr(cur, "description", None) is None:
            return [dict(r) for r in cur.fetchall()]
        return [dict(r) for r in cur.fetchall()] if cur.description else []
    finally:
        cur.close()


def query_one(conn, sql: str, params=None):
    """Like :func:`query` but return the first row dict (or None)."""
    rows = query(conn, sql, params)
    return rows[0] if rows else None


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

    def __init__(self, connection=None, *, connect_timeout: int | None = None):
        if connection is not None:
            if connect_timeout is not None:
                raise ValueError("connect_timeout cannot configure an existing connection")
            self._connection = connection
        else:
            self._connection = get_db() if connect_timeout is None else get_db(connect_timeout=connect_timeout)

    @staticmethod
    def text(sql: str) -> str:
        return sql

    @property
    def autocommit(self) -> bool:
        """Expose transaction mode to helpers that require transaction-local state."""
        return self._connection.autocommit

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

    def cursor(self, *args, **kwargs):
        """Expose DB-API cursors for legacy operations under shared ownership.

        Callers close their cursors; this adapter owns transaction and connection
        cleanup. Named-parameter services should continue using execute().
        """
        return self._connection.cursor(*args, **kwargs)

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


def get_connection(*, connect_timeout: int | None = None) -> DatabaseConnection:
    """Return a transaction-owning credit-service connection."""
    return DatabaseConnection(connect_timeout=connect_timeout)
