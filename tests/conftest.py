"""Shared test fixtures for Kokonut Intelligence tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

PROJECT_DIR = Path(__file__).parent.parent

# Local test runs load the plaintext .env fallback unless CI explicitly opts
# into encrypted secrets. CI still requires KOKONUT_ALLOW_PLAINTEXT_ENV=true
# (or injected secrets) via ci-check.sh; this default only makes `pytest`
# on a dev machine behave like the documented plaintext fallback.
os.environ.setdefault("KOKONUT_ALLOW_PLAINTEXT_ENV", "true")
# Ensure services.common.db resolves the same credentials the compose DB uses.
os.environ.setdefault("POSTGRES_PASSWORD", "dev-kokonut-postgres-2026")


def pytest_sessionfinish(session, exitstatus):
    """Do not allow infrastructure skips to produce a green CI run."""
    if os.environ.get("CI_STRICT_DB") != "1":
        return

    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = terminal_reporter.stats.get("skipped", []) if terminal_reporter else []
    database_skips = [
        report for report in skipped
        if any(marker in str(report.longrepr).lower() for marker in ("no database available", "table not available"))
    ]
    if database_skips:
        print(f"\nERROR: {len(database_skips)} database-dependent tests were skipped in strict CI mode")
        session.exitstatus = 1


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mock helpers (shared across test files to avoid duplication)
# ---------------------------------------------------------------------------

class MockCursor:
    """Reusable mock cursor for unit tests. Tracks call count for sequential fetchall returns."""

    def __init__(self, fetchall_returns: list[list[dict]] | None = None, fetchone_return: dict | None = None):
        self._calls = 0
        self._fetchall_returns = fetchall_returns or []
        self._fetchone_return = fetchone_return or {"name": "Kokonut Adelphi"}
        self._execute_args: list[tuple] = []

    def execute(self, query, params=None):
        self._calls += 1
        self._execute_args.append((query, params))

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
        self._closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        self._closed = True

    def commit(self):
        pass

    def rollback(self):
        pass


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cursor():
    """Shared MockCursor instance."""
    return MockCursor()


@pytest.fixture
def mock_conn(mock_cursor):
    """Shared MockConn wrapping the mock_cursor."""
    return MockConn(cursor=mock_cursor)


@pytest.fixture
def db():
    """Get a database connection, skip if unavailable."""
    try:
        conn = get_db()
        yield conn
        conn.rollback()
        conn.close()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")


# Canonical Kokonut Adelphi location used across the analytics test suite.
ADELPHI_LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture
def location_id() -> str:
    """Return the canonical Adelphi location UUID."""
    return ADELPHI_LOCATION_ID


def assert_sql_contains(path, *fragments: str) -> None:
    """Assert a SQL file contains each fragment (schema-integrity tests)."""
    text = path.read_text()
    missing = [frag for frag in fragments if frag not in text]
    assert not missing, f"{path.name} missing expected fragments: {missing}"


@pytest.fixture
def cli_runner():
    """Run a CLI module's main with given args, return (exit_code, stdout, stderr)."""
    import subprocess

    def _run(module: str, args: list[str] | None = None):
        cmd = [sys.executable, "-m", module] + (args or [])
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
        )
        return result.returncode, result.stdout, result.stderr

    return _run


def assert_public_safe_rows(rows: list[dict]) -> None:
    """Assert that rows from a public view don't contain private fields."""
    private_fields = {"content", "private_notes", "consent_scope", "raw_feedback"}
    for row in rows:
        for field in private_fields:
            assert field not in row or row[field] is None, f"Private field '{field}' exposed in public view row"
