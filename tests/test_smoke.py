"""Smoke test — verify all Python service modules can be imported."""

import subprocess
import sys

MODULES = [
    "services.ingestion.base",
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
]


def test_imports():
    errors = []
    for mod in MODULES:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            print(f"  ✗ {mod}: {e}")
            errors.append((mod, e))
    return errors


def test_cli_parsers():
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


if __name__ == "__main__":
    print("=== Kokonut Intelligence — Smoke Test ===")
    print("\n1. Python imports:")
    import_errors = test_imports()

    print("\n2. CLI parsers:")
    cli_errors = test_cli_parsers()

    print("\n=== Results ===")
    total = len(MODULES) + len(["services.forecast.cli", "services.analytics.cli", "services.revenue_multiplier.cli", "services.fortune500.cli", "services.export.report_generator"])
    errors = import_errors + cli_errors
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
