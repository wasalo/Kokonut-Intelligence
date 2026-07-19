"""Shared CLI infrastructure for Kokonut Intelligence command-line tools.

This module is the single source of truth for cross-cutting CLI concerns so
individual service CLIs stop reinventing the same boilerplate:

* ``run``        — wrap a command so exceptions become a clean ``Error:`` message
                   on stderr and a non-zero process exit code (no raw tracebacks).
* ``print_json`` — one canonical JSON rendering (replaces hundreds of inline
                   ``print(json.dumps(..., default=str))`` copies).
* ``get_connection`` — convenience re-export of the transaction-owning context
                   manager in :mod:`services.common.database`. Use it as
                   ``with get_connection() as conn:`` so connections are always
                   committed/rolled-back and closed, even on error.
* ``mount_argparse`` — adapter that registers an existing argparse-based CLI as a
                   subcommand of the typer meta-CLI without rewriting it.

Usage (new commands)::

    from services.common.cli import run, print_json, get_connection

    def cmd_list():
        with get_connection() as conn:
            rows = conn.execute("SELECT id FROM location").all()
        print_json(rows)

    if __name__ == "__main__":
        run(cmd_list)

Legacy argparse CLIs mount under the meta-CLI via ``mount_argparse``; see
``services/cli.py``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

import typer

from services.common.database import DatabaseConnection, get_connection

__all__ = [
    "run",
    "print_json",
    "get_connection",
    "DatabaseConnection",
    "mount_argparse",
]


def print_json(obj: Any) -> None:
    """Print ``obj`` as indented JSON, tolerating non-serializable values."""
    print(json.dumps(obj, indent=2, default=str))


def run(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Execute ``func`` and translate failures into a clean CLI exit.

    Any exception is reported as ``Error: <message>`` on stderr and the process
    exits with status 1. This keeps callers from leaking raw tracebacks to
    operators while preserving the exit code contract that ``__main__`` blocks
    previously dropped.

    ``argparse.error`` raises ``SystemExit`` internally; that is re-raised
    untouched so argparse's own usage/exit semantics are preserved.
    """
    try:
        func(*args, **kwargs)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report, don't crash
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def mount_argparse(
    app: Any,
    name: str,
    main_factory: Callable[[], Callable[..., Any]],
    help_text: str = "",
) -> None:
    """Register a legacy argparse CLI as a typer subcommand.

    ``main_factory`` returns the legacy CLI's ``main`` callable (e.g.
    ``lambda: services.metrics.cli.main``). The adapter rewrites ``sys.argv`` so
    the legacy ``main()`` (which parses ``sys.argv`` itself) sees only the
    tokens after the subcommand name, then calls it and re-raises its
    ``SystemExit`` so help text and exit codes propagate.

    This lets the 100+ existing argparse CLIs join the unified ``kokonut``
    command tree without a full rewrite and without touching their code.
    """

    def _wrapper(ctx: "typer.Context") -> None:
        # typer has already consumed the subcommand name; ``ctx.args`` holds the
        # tokens that follow it. Feed those to the legacy parser via sys.argv.
        rest = list(ctx.args) if ctx is not None else []
        saved = sys.argv
        try:
            sys.argv = [saved[0] if saved else "kokonut", *rest]
            run(main_factory())
        except SystemExit:
            raise
        finally:
            sys.argv = saved

    # Accept a leading variadic argument so typer does not error on unknown
    # options belonging to the legacy parser.
    app.command(
        name=name,
        help=help_text,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )(_wrapper)
