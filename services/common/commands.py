"""Declarative subcommand CLI framework for Kokonut services.

A thin, convention-driven layer on top of :mod:`services.common.cli` that
removes the per-module boilerplate legacy analytics/services CLIs reimplement
by hand:

* argument parsing — subcommands are declared, an argparse parser is built
  from the declarations (identical flags, defaults, dests);
* database lifecycle — one connection is opened per invocation and always
  closed, even when the handler raises; commands that are pure computations
  opt out with ``run(handler, needs_db=False)``;
* output — results are rendered with the canonical ``print_json`` by default;
  commands with human-readable output provide their own ``render``;
* error handling — ``CommandLine.run`` wraps dispatch with
  :func:`services.common.cli.run`, so failures become a clean ``Error:``
  message and exit code 1 instead of a raw traceback.

Usage::

    from services.common.commands import CommandLine

    cli = CommandLine("digital_finance", "Digital financial services")

    cli.subcommand("balance", "Get account balance") \\
        .add("--account-id", required=True) \\
        .run(lambda db, args: get_account_balance(db, args.account_id))

    if __name__ == "__main__":
        cli.run()

Modules can keep their documented ``main()`` entry point for backwards
compatibility (the meta-CLI mounts legacy CLIs through ``main``)::

    def main(argv=None):
        cli.run(argv)

    if __name__ == "__main__":
        main()
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from services.common.cli import print_json, run
from services.common.database import get_db

__all__ = ["Argument", "Subcommand", "CommandLine"]


def _default_render(result: Any, args: argparse.Namespace) -> None:
    """Default renderer: canonical JSON output."""
    print_json(result)


@dataclass
class Argument:
    """One ``add_argument`` declaration (names + kwargs), applied verbatim."""

    names: tuple[str, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Subcommand:
    """A declared subcommand: argparse surface, handler, and renderer."""

    name: str
    help: str = ""
    argspecs: list[Argument] = field(default_factory=list)
    handler: Optional[Callable[[Any, argparse.Namespace], Any]] = None
    needs_db: bool = True
    render: Callable[[Any, argparse.Namespace], None] = staticmethod(
        _default_render
    )

    def add(self, *names: str, **kwargs: Any) -> "Subcommand":
        """Declare an argument exactly like :meth:`argparse.ArgumentParser.add_argument`."""
        self.argspecs.append(Argument(tuple(names), kwargs))
        return self

    def run(
        self,
        handler: Callable[[Any, argparse.Namespace], Any],
        needs_db: bool = True,
    ) -> "Subcommand":
        """Bind the handler. Signature: ``handler(conn, args) -> result``.

        Set ``needs_db=False`` for pure-computation commands that should run
        without opening a database connection (``conn`` is passed as ``None``).
        """
        self.handler = handler
        self.needs_db = needs_db
        return self

    def render_with(self, render: Callable[[Any, argparse.Namespace], None]) -> "Subcommand":
        """Bind a custom renderer (e.g. human-readable output)."""
        self.render = render
        return self


class CommandLine:
    """A declarative argparse-based subcommand CLI.

    ``prog`` defaults to ``sys.argv[0]`` to match legacy behavior.
    ``connection_factory`` defaults to the canonical raw psycopg2
    :func:`services.common.database.get_db`; the connection is closed in a
    ``finally`` block after the handler runs (or fails).
    """

    def __init__(
        self,
        prog: Optional[str] = None,
        description: str = "",
        connection_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.prog = prog or (sys.argv[0] if sys.argv else "kokonut")
        self.description = description
        self._commands: list[Subcommand] = []
        self._connection_factory = connection_factory or get_db

    def subcommand(self, name: str, help: str = "") -> Subcommand:
        """Declare a subcommand; chain ``.add(...)`` then ``.run(handler)``."""
        subcommand = Subcommand(name=name, help=help)
        self._commands.append(subcommand)
        return subcommand

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=self.prog, description=self.description)
        sub = parser.add_subparsers(dest="command")
        for command in self._commands:
            sub_parser = sub.add_parser(command.name, help=command.help)
            for argument in command.argspecs:
                sub_parser.add_argument(*argument.names, **argument.kwargs)
        return parser

    def main(self, argv: Optional[list[str]] = None) -> None:
        """Parse argv, dispatch the subcommand, and render the result."""
        parser = self.build_parser()
        args = parser.parse_args(argv)
        command_name = getattr(args, "command", None)
        if command_name is None:
            parser.print_help()
            return
        command = next(c for c in self._commands if c.name == command_name)
        conn = self._connection_factory() if command.needs_db else None
        try:
            result = command.handler(conn, args)
        finally:
            if conn is not None:
                conn.close()
        command.render(result, args)

    def run(self, argv: Optional[list[str]] = None) -> None:
        """Dispatch via :func:`services.common.cli.run` for clean error handling."""
        run(self.main, argv)
