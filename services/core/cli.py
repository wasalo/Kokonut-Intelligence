"""Read-only Kernel operator commands."""

from __future__ import annotations

import typer

from services.common.cli import print_json, run

app = typer.Typer(help=__doc__, no_args_is_help=True, add_completion=False)


@app.callback()
def kernel() -> None:
    """Inspect Kernel preparation without starting runtime processes."""


def report_schema_readiness() -> None:
    from services.core.schema_readiness import SchemaReadinessError, require_schema_ready

    try:
        counts = require_schema_ready()
    except SchemaReadinessError as exc:
        print_json({"ready": False, "code": exc.code, **exc.counts})
        raise SystemExit(1) from exc
    except Exception as exc:
        # Never pass database/file exception text through the generic CLI wrapper.
        print_json({"ready": False, "code": "probe_unavailable",
                    "error_type": type(exc).__name__})
        raise SystemExit(1) from exc
    print_json({"ready": True, "code": "ready", **counts})


@app.command("schema-readiness")
def schema_readiness() -> None:
    """Check bundled schema checksums and required PostgreSQL extensions."""
    run(report_schema_readiness)


if __name__ == "__main__":
    app()
