"""Unified Kokonut Intelligence command-line interface.

This typer-based meta-CLI is the single entry point for all Kokonut service
CLIs. It is invoked as::

    python3 -m services.cli --help
    python3 -m services.cli metrics --list
    python3 -m services.cli threatcasting --list-threats --location-id UUID

Legacy argparse-based service CLIs are mounted unchanged via
:func:`services.common.cli.mount_argparse`; their existing
``python3 -m services.metrics.cli`` invocations continue to work independently.

New service groups should be added here as native typer subcommands using the
shared helpers in :mod:`services.common.cli` (``run``, ``print_json``,
``get_connection``).
"""

from __future__ import annotations

import importlib
from typing import Callable

import typer

from services.common.cli import mount_argparse

app = typer.Typer(
    name="kokonut",
    help="Kokonut Intelligence unified CLI",
    no_args_is_help=True,
    add_completion=False,
)


def _legacy(module_path: str, attr: str = "main") -> Callable:
    """Return a factory that lazily fetches ``module.attr`` (the legacy main).

    Import errors surface as a clean ``Error:`` message rather than a raw
    traceback, so one service with a missing optional dependency does not break
    the whole CLI.
    """

    def _factory() -> Callable[..., Any]:
        try:
            module = importlib.import_module(module_path)
            return getattr(module, attr)
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            import sys

            print(f"Error: cannot load {module_path}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    return _factory


# --- Core / high-traffic services mounted as-is (argparse) -------------------
_MOUNTED = [
    ("metrics", "services.metrics.cli", "Metric computation engine"),
    ("attestation", "services.attestation.cli", "EAS attestation operations"),
    ("forecast", "services.forecast.cli", "Forecast engine"),
    ("delphi", "services.delphi.cli", "Real-time Delphi consultations"),
    ("threatcasting", "services.threatcasting.cli", "Threatcasting & backcasting"),
    ("migration", "services.migration.cli", "Schema migration runner"),
    ("crisp", "services.crisp.cli", "CRISP risk scoring"),
    ("analytics", "services.analytics.cli", "General analytics commands"),
    ("ingestion", "services.ingestion.cli", "Ingestion pipelines"),
    ("agents", "services.agents.cli", "Agent task catalogue"),
    ("export", "services.export.cli", "Report generation & exports"),
    ("systems", "services.systems.cli", "Systems-thinking tooling"),
    ("governance", "services.analytics.cli_governance_roles", "Governance role commands"),
]

for _name, _mod, _help in _MOUNTED:
    mount_argparse(app, _name, _legacy(_mod), _help)


# --- Native typer group: DAO governance framework queries (read-only) --------
try:
    from services.governance.cli import app as _governance_dao_app

    app.add_typer(_governance_dao_app, name="dao", help="DAO governance framework queries (Baal/Moloch, read-only)")
except Exception as exc:  # noqa: BLE001 - CLI boundary
    import sys

    print(f"Error: cannot load services.governance.cli: {exc}", file=sys.stderr)


# --- Example native typer group using shared helpers -------------------------
@app.command()
def health() -> None:
    """Show overall platform health summary."""
    from services.common.cli import get_connection, print_json, run

    def _go() -> None:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT count(*) AS location_count FROM location"
            ).all()
        print_json(rows[0] if rows else {})

    run(_go)


if __name__ == "__main__":
    app()
