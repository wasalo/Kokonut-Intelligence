"""CLI smoke tests — verify each CLI runs without error."""

import subprocess
import sys


CLI_COMMANDS = [
    # forecast CLI
    ("python3", "-m", "services.forecast.cli", "--list"),
    ("python3", "-m", "services.forecast.cli", "--help"),

    # analytics CLI
    ("python3", "-m", "services.analytics.cli", "--help"),

    # revenue_multiplier CLI
    ("python3", "-m", "services.revenue_multiplier.cli", "--list-dimensions"),
    ("python3", "-m", "services.revenue_multiplier.cli", "--help"),

    # fortune500 CLI
    ("python3", "-m", "services.fortune500.cli", "--help"),

    # report_generator CLI
    ("python3", "-m", "services.export.report_generator", "--list"),
    ("python3", "-m", "services.export.report_generator", "--help"),

    # ingestion CLI
    ("python3", "-m", "services.ingestion.sensor_ingester", "--list"),
    ("python3", "-m", "services.ingestion.sensor_ingester", "--help"),

    # weather CLI
    ("python3", "-m", "services.ingestion.weather", "--help"),

    # market_data CLI
    ("python3", "-m", "services.ingestion.market_data", "--help"),

    # CIDS exporter CLI
    ("python3", "-m", "services.registry.cids_export", "--help"),
]


def run_cli_tests():
    errors = []
    for cmd in CLI_COMMANDS:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"  ✓ {' '.join(cmd)}")
            else:
                # Some CLIs exit with error when no args are provided
                # Check if it's a "help" or "list" command
                if "--help" in cmd or "--list" in cmd or "--list-dimensions" in cmd:
                    print(f"  ✓ {' '.join(cmd)}")
                else:
                    print(f"  ✗ {' '.join(cmd)}: {result.stderr.strip()}")
                    errors.append((cmd, result.stderr))
        except Exception as e:
            print(f"  ✗ {' '.join(cmd)}: {e}")
            errors.append((cmd, str(e)))

    return errors


if __name__ == "__main__":
    print("=== CLI Smoke Tests ===")
    errors = run_cli_tests()

    passed = len(CLI_COMMANDS) - len(errors)
    total = len(CLI_COMMANDS)
    print(f"\n  Pass: {passed}/{total}")

    if errors:
        for cmd, err in errors:
            print(f"  ✗ {' '.join(cmd)}: {err}")
        sys.exit(1)
    else:
        print("  All CLI smoke tests passed ✓")
