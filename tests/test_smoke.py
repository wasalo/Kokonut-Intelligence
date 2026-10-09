"""Smoke test — verify all Python service modules can be imported."""

import subprocess
import sys

MODULES = [
    "services.ingestion.base",
    "services.ingestion.remote_sensing",
    "services.forecast.engine",
    "services.forecast.cli",
    "services.forecast.pricing",
    "services.forecast.yield_forecast",
    "services.forecast.cost_forecast",
    "services.forecast.risk",
    "services.analytics.ecology",
    "services.analytics.cli",
    "services.fortune500.calculator",
    "services.fortune500.cli",
    "services.revenue_multiplier.analyzer",
    "services.revenue_multiplier.cli",
    "services.export.report_generator",
    "services.export.exporter",
    "services.metrics.engine",
    "services.metrics.cli",
    "services.events.bus",
    "services.events.handlers",
    "services.events.cli",
    "services.scheduler.engine",
    "services.scheduler.worker",
    "services.scheduler.cli",
    "services.scheduler.parser",
    "services.scheduler.resources",
    "services.cache.cache",
    "services.cache.events",
    "services.drivers.protocol",
    "services.drivers.base",
    "services.drivers.registry",
    "services.drivers.cli",
    "services.core.features",
    "services.core.health",
    "services.stream.processor",
    "services.stream.windows",
    "services.stream.alerts",
    "services.stream.buffer",
    "services.stream.cli",
    "services.security.capabilities",
    "services.security.audit",
    "services.security.interceptor",
    "services.security.cli",
    "services.federation.node",
    "services.federation.protocol",
    "services.federation.sync",
    "services.federation.cli",
    "services.sandbox.environment",
    "services.sandbox.isolation",
    "services.sandbox.monitor",
    "services.sandbox.cli",
    "services.gateway.auth",
    "services.gateway.rate_limiter",
    "services.gateway.audit",
    "services.gateway.router",
    "services.gateway.cli",
]


def run_imports():
    errors = []
    for mod in MODULES:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            print(f"  ✗ {mod}: {e}")
            errors.append((mod, e))
    return errors


def test_imports() -> None:
    errors = run_imports()
    assert not errors, f"Import checks failed: {errors}"


def run_cli_parsers():
    """Verify CLI modules have valid argparse parsers."""
    import importlib

    clis = [
        "services.forecast.cli",
        "services.analytics.cli",
        "services.revenue_multiplier.cli",
        "services.fortune500.cli",
        "services.export.report_generator",
    ]

    errors = []
    for mod_name in clis:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "main"):
                # Test that argparse can be instantiated without error
                import sys
                old_argv = sys.argv
                sys.argv = [mod_name]
                try:
                    mod.main()
                except SystemExit as e:
                    if e.code not in (0, None):
                        pass  # argparse exit on no args is OK
                finally:
                    sys.argv = old_argv
                print(f"  ✓ {mod_name} CLI parser")
            else:
                print(f"  ⚠ {mod_name} has no main()")
        except Exception as e:
            print(f"  ✗ {mod_name} CLI: {e}")
            errors.append((mod_name, e))
    return errors


def test_cli_parsers() -> None:
    errors = run_cli_parsers()
    assert not errors, f"CLI parser checks failed: {errors}"


def test_remote_sensing_bbox_parse():
    """Remote sensing CSV parser keeps bbox from raw row fields."""
    from services.ingestion.remote_sensing import parse_row

    record = parse_row({
        "plot_id": "00000000-0000-0000-0000-000000000001",
        "observation_date": "2026-01-01",
        "source": "sentinel-2",
        "bbox_west": "1",
        "bbox_south": "2",
        "bbox_east": "3",
        "bbox_north": "4",
    }, "00000000-0000-0000-0000-000000000002")
    assert record["bbox"] == "SRID=4326;POLYGON((1.0 2.0,3.0 2.0,3.0 4.0,1.0 4.0,1.0 2.0))"


def test_exporter_defaults_governed_filters():
    """Governed exports default to verified/published records."""
    from services.export.exporter import Exporter

    exporter = Exporter()
    filters = exporter._apply_default_governance_filter("harvest_event", None, include_drafts=False)
    assert filters == {"status": {"$in": ["verified", "published"]}}
    assert exporter._apply_default_governance_filter("harvest_event", {"status": "draft"}, False)["status"] == "draft"
    assert exporter._apply_default_governance_filter("harvest_event", None, include_drafts=True) is None


if __name__ == "__main__":
    print("=== Kokonut Intelligence — Smoke Test ===")
    print("\n1. Python imports:")
    import_errors = run_imports()

    print("\n2. CLI parsers:")
    cli_errors = run_cli_parsers()

    print("\n3. Remote sensing parser:")
    parser_errors = []
    try:
        test_remote_sensing_bbox_parse()
        print("  ✓ remote sensing bbox parse")
    except Exception as e:
        print(f"  ✗ remote sensing bbox parse: {e}")
        parser_errors.append(("remote sensing bbox parse", e))

    print("\n4. Exporter governance defaults:")
    try:
        test_exporter_defaults_governed_filters()
        print("  ✓ exporter governance defaults")
    except Exception as e:
        print(f"  ✗ exporter governance defaults: {e}")
        parser_errors.append(("exporter governance defaults", e))

    print("\n=== Results ===")
    total = len(MODULES) + len(["services.forecast.cli", "services.analytics.cli", "services.revenue_multiplier.cli", "services.fortune500.cli", "services.export.report_generator"]) + 2
    errors = import_errors + cli_errors + parser_errors
    passed = total - len(errors)
    print(f"  Pass: {passed}/{total}")
    if errors:
        print(f"  Fail: {len(errors)}")
        for mod, e in errors:
            print(f"    {mod}: {e}")
        sys.exit(1)
    else:
        print("  All smoke tests passed ✓")
        sys.exit(0)
