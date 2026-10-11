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


def report_overview() -> None:
    """Report local provider selection without probing services or reading secrets."""
    from services import __git_sha__, __version__
    from services.core.features import list_features

    providers = [
        {
            "name": feature["name"],
            "category": feature.get("category", "uncategorized"),
            "enabled": bool(feature.get("enabled", False)),
            "critical": bool(feature.get("critical", False)),
        }
        for feature in list_features()
    ]
    providers.sort(key=lambda feature: feature["name"])
    print_json({
        "kind": "kernel_configuration_overview",
        "health_checked": False,
        "database_checked": False,
        "platform": {
            "name": "Kokonut Intelligence",
            "version": __version__,
            "git_sha": __git_sha__,
        },
        "providers": providers,
    })


@app.command("overview")
def overview() -> None:
    """Show build metadata and provider selection without runtime probes."""
    run(report_overview)


@app.command("schema-readiness")
def schema_readiness() -> None:
    """Check bundled schema checksums and required PostgreSQL extensions."""
    run(report_schema_readiness)


if __name__ == "__main__":
    app()
