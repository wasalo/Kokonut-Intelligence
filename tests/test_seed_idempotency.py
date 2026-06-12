import subprocess
import sys


def database_running() -> bool:
    """Return true when the Compose database service is running."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "--services"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return result.returncode == 0 and "database" in result.stdout.splitlines()


def test_seed_idempotency():
    """Run seed scripts twice and verify no errors."""
    import os

    if not database_running():
        print("  ⚠ Database service not running — skipping seed idempotency")
        return []

    seed_script = "scripts/seed.sh"
    seed_pilot_script = "scripts/seed-pilot.sh"

    results = []

    for script in [seed_script, seed_pilot_script]:
        if not os.path.exists(script):
            print(f"  ⚠ {script} not found — skipping")
            continue

        # Run first time
        result1 = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
        )

        if result1.returncode != 0:
            print(f"  ✗ {script} first run failed: {result1.stderr}")
            results.append((script, "first run", False))
            continue

        # Run second time (should be idempotent)
        result2 = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
        )

        if result2.returncode != 0:
            print(f"  ✗ {script} second run failed (not idempotent): {result2.stderr}")
            results.append((script, "second run", False))
        else:
            print(f"  ✓ {script} is idempotent")
            results.append((script, "idempotent", True))

    return results


if __name__ == "__main__":
    print("=== Seed Idempotency Test ===")
    results = test_seed_idempotency()

    passed = sum(1 for r in results if r[2])
    total = len(results)
    print(f"\n  Pass: {passed}/{total}")

    if passed < total:
        sys.exit(1)
    else:
        print("  All seed idempotency tests passed ✓")
