"""Shared test fixtures for Kokonut Intelligence tests."""

import os
import subprocess
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras


PROJECT_DIR = Path(__file__).parent.parent


def database_running() -> bool:
    """Check if the PostgreSQL Docker service is running."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"),
             "ps", "--status", "running", "--services"],
            capture_output=True, text=True, timeout=10,
        )
        return "database" in result.stdout.strip()
    except Exception:
        return False


def get_db():
    """Get a direct PostgreSQL connection for integration tests."""
    from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )


class MockCursor:
    """Reusable mock cursor for unit tests. Tracks call count for sequential fetchall returns."""

    def __init__(self, fetchall_returns: list[list[dict]] | None = None, fetchone_return: dict | None = None):
        self._calls = 0
        self._fetchall_returns = fetchall_returns or []
        self._fetchone_return = fetchone_return or {"name": "Kokonut Adelphi"}

    def execute(self, query, params=None):
        self._calls += 1

    def fetchone(self):
        return self._fetchone_return

    def fetchall(self):
        if self._calls <= len(self._fetchall_returns):
            return self._fetchall_returns[self._calls - 1]
        return []

    def close(self):
        pass


class MockConn:
    """Reusable mock connection that returns MockCursor instances."""

    def __init__(self, cursor: MockCursor | None = None):
        self._cursor = cursor or MockCursor()

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        pass

    def commit(self):
        pass


def assert_public_safe_rows(rows: list[dict]) -> None:
    """Assert that rows from a public view don't contain private fields."""
    private_fields = {"content", "private_notes", "consent_scope", "raw_feedback"}
    for row in rows:
        for field in private_fields:
            assert field not in row or row[field] is None, f"Private field '{field}' exposed in public view row"
