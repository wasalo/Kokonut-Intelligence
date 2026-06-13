import json
import subprocess
import sys
from pathlib import Path


SNAPSHOT_PATH = Path("schemas/directus/snapshots/schema_latest.json")


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


def snapshot_drift() -> list[str]:
    """Validate Directus snapshot collection metadata against physical fields."""
    if not SNAPSHOT_PATH.exists():
        print("  ⚠ Snapshot file not found — skipping snapshot drift check")
        return []
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    data = snapshot["data"]
    physical_fields = {
        (field["collection"], field["field"])
        for field in data.get("fields", [])
        if field.get("schema") is not None
    }

    errors: list[str] = []
    for collection in data.get("collections", []):
        if (collection.get("meta") or {}).get("system"):
            continue
        collection_name = collection["collection"]
        sort_field = (collection.get("meta") or {}).get("sort_field")
        if sort_field and (collection_name, sort_field) not in physical_fields:
            errors.append(f"{collection_name}.sort_field points to missing field {sort_field}")

    for field in data.get("fields", []):
        meta = field.get("meta") or {}
        special = meta.get("special") or field.get("special") or ""
        if field.get("schema") is None and "alias" not in special:
            errors.append(f"{field['collection']}.{field['field']} has non-alias metadata without a DB field")

    return errors


def live_drift() -> list[str]:
    """Validate live Directus metadata when Postgres is running."""
    if not database_running():
        print("  ⚠ Database service not running — skipping live Directus metadata check")
        return []

    sql = """
WITH invalid_sort AS (
    SELECT dc.collection || '.sort_field=' || dc.sort_field AS issue
    FROM directus_collections dc
    WHERE dc.sort_field IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM information_schema.columns c
          WHERE c.table_schema = 'public'
            AND c.table_name = dc.collection
            AND c.column_name = dc.sort_field
      )
), stale_fields AS (
    SELECT df.collection || '.' || df.field AS issue
    FROM directus_fields df
    WHERE EXISTS (
          SELECT 1
          FROM information_schema.tables t
          WHERE t.table_schema = 'public'
            AND t.table_name = df.collection
      )
      AND NOT EXISTS (
          SELECT 1
          FROM information_schema.columns c
          WHERE c.table_schema = 'public'
            AND c.table_name = df.collection
            AND c.column_name = df.field
      )
      AND COALESCE(df.special, '') NOT LIKE '%alias%'
)
SELECT issue FROM invalid_sort
UNION ALL
SELECT issue FROM stale_fields
ORDER BY issue;
"""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "database",
            "psql",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-At",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return [result.stderr.strip() or "live Directus metadata query failed"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_directus_metadata() -> list[tuple[str, bool, list[str]]]:
    checks = [
        ("snapshot", snapshot_drift()),
        ("live", live_drift()),
    ]
    results = []
    for name, errors in checks:
        if errors:
            print(f"  ✗ Directus {name} metadata drift:")
            for error in errors:
                print(f"    - {error}")
            results.append((name, False, errors))
        else:
            print(f"  ✓ Directus {name} metadata is aligned")
            results.append((name, True, []))
    return results


if __name__ == "__main__":
    print("=== Directus Metadata Test ===")
    results = test_directus_metadata()

    passed = sum(1 for result in results if result[1])
    total = len(results)
    print(f"\n  Pass: {passed}/{total}")

    if passed < total:
        sys.exit(1)
    print("  Directus metadata checks passed ✓")
