"""Tests for the shared declarative subcommand framework (services.common.commands).

The framework builds on :mod:`services.common.cli`, whose import chain loads the
environment; set the plaintext opt-in flag up front (as CI does) so the tests
run in sandboxes without SOPS access.
"""

from __future__ import annotations

import contextlib
import io
import json
import os

os.environ.setdefault("KOKONUT_ALLOW_PLAINTEXT_ENV", "true")

import sys  # noqa: E402

import pytest  # noqa: E402

from services.common.commands import CommandLine  # noqa: E402


class _FakeConn:
    """Minimal stand-in for the psycopg2 connection the framework closes."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _capture_stdout(fn) -> tuple[str, list]:
    out = io.StringIO()
    conns: list = []

    def factory() -> _FakeConn:
        conn = _FakeConn()
        conns.append(conn)
        return conn

    cli = CommandLine("prog", "test cli", connection_factory=factory)
    cli.subcommand("hi", "Say hi") \
        .add("--name", required=True) \
        .run(lambda db, a: {"hello": a.name})
    with contextlib.redirect_stdout(out):
        fn(cli)
    return out.getvalue(), conns


def test_dispatches_and_renders_json() -> None:
    """Handler result is rendered as canonical JSON with parsed args."""

    def run(cli) -> None:
        cli.main(["hi", "--name", "world"])

    output, conns = _capture_stdout(run)
    assert json.loads(output) == {"hello": "world"}
    assert len(conns) == 1


def test_connection_closed_after_success() -> None:
    _, conns = _capture_stdout(lambda cli: cli.main(["hi", "--name", "x"]))
    assert conns[0].closed is True


def test_connection_closed_on_handler_error() -> None:
    conns: list = []

    def factory() -> _FakeConn:
        conn = _FakeConn()
        conns.append(conn)
        return conn

    cli = CommandLine("prog", "test", connection_factory=factory)
    cli.subcommand("boom", "boom") \
        .run(lambda db, a: (_ for _ in ()).throw(RuntimeError("kaboom")))

    with pytest.raises(RuntimeError, match="kaboom"):
        cli.main(["boom"])
    assert conns[0].closed is True


def test_run_wraps_errors_cleanly() -> None:
    """run() turns handler exceptions into Error: + exit code 1 (via cli.run)."""

    def factory() -> _FakeConn:
        return _FakeConn()

    cli = CommandLine("prog", "test", connection_factory=factory)
    cli.subcommand("boom", "boom") \
        .run(lambda db, a: (_ for _ in ()).throw(RuntimeError("kaboom")))

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        with pytest.raises(SystemExit) as excinfo:
            cli.run(["boom"])
    assert excinfo.value.code == 1
    assert "Error: kaboom" in err.getvalue()


def test_custom_render_used() -> None:
    out = io.StringIO()
    seen = []

    def factory() -> _FakeConn:
        return _FakeConn()

    cli = CommandLine("prog", "test", connection_factory=factory)

    def render(result, args) -> None:
        seen.append((result, args))
        print("custom!")

    cli.subcommand("raw", "raw") \
        .run(lambda db, a: {"x": 1}) \
        .render_with(render)
    with contextlib.redirect_stdout(out):
        cli.main(["raw"])
    assert out.getvalue().strip() == "custom!"
    assert seen[0][0] == {"x": 1}


def test_no_command_prints_help() -> None:
    out = io.StringIO()
    cli = CommandLine("prog", "test", connection_factory=lambda: _FakeConn())
    cli.subcommand("hi", "Say hi") \
        .add("--name", required=True) \
        .run(lambda db, a: {"hello": a.name})
    with contextlib.redirect_stdout(out):
        cli.main([])
    assert "usage:" in out.getvalue()
    assert "hi" in out.getvalue()


def test_required_arg_error_preserved() -> None:
    """argparse's SystemExit (usage error) propagates unchanged."""

    def factory() -> _FakeConn:
        return _FakeConn()

    cli = CommandLine("prog", "test", connection_factory=factory)
    cli.subcommand("hi", "Say hi") \
        .add("--name", required=True) \
        .run(lambda db, a: {"hello": a.name})
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["hi"])
    assert excinfo.value.code == 2
