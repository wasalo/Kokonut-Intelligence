#!/usr/bin/env python3
"""Exercise the Kokonut Network operating-tenant map in disposable PostgreSQL."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.mobile.tenant_preflight import (  # noqa: E402
    _CONFIRMED_OPERATING_TENANT_MAP_SQL,
)

SEED = ROOT / "schemas" / "seeds" / "122_kokonut_network_operating_tenant_map.sql"
EVIDENCE = (
    ROOT
    / "docs"
    / "refactor"
    / "builds"
    / "2026-10-16-recovery"
    / "network-location-owner-map-disposable.json"
)
OWNER_ID = "a0000000-0000-0000-0000-000000000701"
OTHER_ORG_ID = "a0000000-0000-0000-0000-000000000800"

FIXTURE = """
CREATE TABLE organization (
    id uuid PRIMARY KEY,
    org_key text UNIQUE NOT NULL,
    name text NOT NULL,
    status text NOT NULL
);
CREATE TABLE location (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    slug text UNIQUE NOT NULL,
    organization_id uuid REFERENCES organization(id),
    status text NOT NULL DEFAULT 'active'
);
CREATE TABLE organization_member (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organization(id),
    location_id uuid NOT NULL REFERENCES location(id),
    membership_type text NOT NULL,
    role text NOT NULL,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE location_tenant_owner_verification (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id uuid NOT NULL REFERENCES location(id),
    organization_id uuid NOT NULL REFERENCES organization(id),
    decision_reference text NOT NULL UNIQUE,
    confirmed_by text NOT NULL,
    confirmed_at timestamptz NOT NULL,
    revoked_at timestamptz
);
CREATE UNIQUE INDEX active_owner_confirmation
    ON location_tenant_owner_verification (location_id)
    WHERE revoked_at IS NULL;
INSERT INTO organization VALUES
    ('a0000000-0000-0000-0000-000000000701', 'kokonut-network', 'Kokonut Network', 'active'),
    ('a0000000-0000-0000-0000-000000000800', 'other-org', 'Other Organization', 'active');
INSERT INTO location VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Kokonut Adelphi', 'kokonut-adelphi', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000002', 'Kokonut Genesis', 'kokonut-genesis', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000099', 'Unmapped Location', 'unmapped-location', NULL);
INSERT INTO organization_member (
    id, organization_id, location_id, membership_type, role, status, metadata
) VALUES
    ('a0000000-0000-0000-0000-000000000711', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000001', 'owned', 'primary', 'active', '{"ownership_reconciliation":"owner_confirmed"}'),
    ('a0000000-0000-0000-0000-000000000712', 'a0000000-0000-0000-0000-000000000701', 'a0000000-0000-0000-0000-000000000002', 'owned', 'primary', 'active', '{"ownership_reconciliation":"owner_confirmed"}');
INSERT INTO location_tenant_owner_verification (
    location_id, organization_id, decision_reference, confirmed_by, confirmed_at
) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701', 'existing-confirmation:adelphi', 'repository owner', '2026-10-13T12:00:00Z'),
    ('a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000701', 'existing-confirmation:genesis', 'repository owner', '2026-10-13T12:00:00Z');
"""


def run(args: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def sql(container: str, statement: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X",
            "-v", "ON_ERROR_STOP=1", "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
        check=check,
    )


def value(container: str, statement: str) -> str:
    return sql(container, statement).stdout.strip()


def assert_value(container: str, statement: str, expected: str, label: str) -> None:
    actual = value(container, statement)
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, got {actual!r}")


def seed(container: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return sql(container, SEED.read_text(), check=check)


def owner_map_values(container: str) -> list[int]:
    output = sql(container, _CONFIRMED_OPERATING_TENANT_MAP_SQL).stdout.strip()
    values = output.split("|")
    if len(values) != 6:
        raise RuntimeError(f"owner-map preflight returned an unexpected row: {output!r}")
    return [int(value) for value in values]


def wait_ready(container: str) -> None:
    for _ in range(60):
        result = run(["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    suffix = uuid.uuid4().hex[:10]
    container = f"kokonut-owner-map-{suffix}"
    started = False
    checks: list[dict[str, str]] = []
    try:
        run(
            [
                "docker", "run", "--detach", "--rm", "--name", container,
                "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16",
            ]
        )
        started = True
        wait_ready(container)
        sql(container, FIXTURE)

        seed(container)
        assert_value(
            container,
            "SELECT count(*) FROM location_tenant_owner_verification WHERE revoked_at IS NULL",
            "2",
            "absent planned locations are skipped",
        )
        if owner_map_values(container) != [5, 2, 2, 3, 0, 0]:
            raise RuntimeError("aggregate preflight did not report two confirmed and three missing locations")
        checks.append({"id": "missing_future_locations", "result": "passed"})

        sql(
            container,
            """
            INSERT INTO location (id, name, slug) VALUES
                ('a0000000-0000-0000-0000-000000000003', 'Kokonut Seeds', 'kokonut-seeds'),
                ('a0000000-0000-0000-0000-000000000004', 'Kokonut Terra Viva', 'kokonut-terra-viva'),
                ('a0000000-0000-0000-0000-000000000005', 'Kokonut V1', 'kokonut-v1');
            """,
        )
        seed(container)
        assert_value(
            container,
            """
            SELECT count(*)
              FROM location AS loc
              JOIN organization AS org ON org.id = loc.organization_id
             WHERE org.org_key = 'kokonut-network'
               AND loc.slug IN ('kokonut-genesis', 'kokonut-seeds', 'kokonut-adelphi', 'kokonut-terra-viva', 'kokonut-v1')
            """,
            "5",
            "all owner-confirmed locations map to the canonical tenant",
        )
        assert_value(
            container,
            """
            SELECT count(*) FROM (
                SELECT loc.id
                  FROM location AS loc
                  JOIN organization_member AS member ON member.location_id = loc.id
                 WHERE loc.slug LIKE 'kokonut-%'
                   AND member.organization_id = 'a0000000-0000-0000-0000-000000000701'
                   AND member.membership_type = 'owned' AND member.status = 'active'
                 GROUP BY loc.id HAVING count(*) = 1
            ) AS one_active_owner
            """,
            "5",
            "one active owner relationship per mapped location",
        )
        assert_value(
            container,
            "SELECT count(*) FROM location_tenant_owner_verification WHERE revoked_at IS NULL",
            "5",
            "active owner verification exists for every mapped location",
        )
        assert_value(
            container,
            "SELECT count(*) FROM location WHERE slug = 'unmapped-location' AND organization_id IS NULL",
            "1",
            "unmapped locations remain unassigned",
        )
        if owner_map_values(container) != [5, 5, 5, 0, 0, 0]:
            raise RuntimeError("aggregate preflight did not report all five exact verified locations")
        checks.append({"id": "five_location_mapping", "result": "passed"})

        sql(
            container,
            "UPDATE location SET status = 'inactive' WHERE slug = 'kokonut-v1';",
        )
        if owner_map_values(container) != [5, 5, 4, 0, 0, 1]:
            raise RuntimeError("aggregate preflight counted an inactive location as owner-confirmed")
        sql(
            container,
            "UPDATE location SET status = 'active' WHERE slug = 'kokonut-v1';",
        )
        checks.append({"id": "inactive_location_not_owner_confirmed", "result": "passed"})

        seed(container)
        assert_value(
            container,
            "SELECT count(*) FROM organization_member WHERE status = 'active' AND membership_type = 'owned'",
            "5",
            "replay does not duplicate ownership relationships",
        )
        assert_value(
            container,
            "SELECT count(*) FROM location_tenant_owner_verification WHERE revoked_at IS NULL",
            "5",
            "replay does not duplicate current owner confirmations",
        )
        if owner_map_values(container) != [5, 5, 5, 0, 0, 0]:
            raise RuntimeError("aggregate preflight changed after idempotent replay")
        checks.append({"id": "idempotent_replay", "result": "passed"})

        sql(
            container,
            "UPDATE location SET organization_id = NULL WHERE slug = 'kokonut-genesis'; UPDATE location SET name = 'Wrong Name' WHERE slug = 'kokonut-seeds';",
        )
        failed_name = seed(container, check=False)
        if failed_name.returncode == 0 or "Known location slug kokonut-seeds has an unexpected name" not in failed_name.stderr:
            raise RuntimeError("unexpected name mismatch did not fail closed")
        assert_value(
            container,
            "SELECT organization_id IS NULL FROM location WHERE slug = 'kokonut-genesis'",
            "t",
            "name mismatch rolls back prior location changes",
        )
        sql(container, "UPDATE location SET name = 'Kokonut Seeds' WHERE slug = 'kokonut-seeds';")
        checks.append({"id": "identity_mismatch_rollback", "result": "passed"})

        sql(
            container,
            f"UPDATE location SET organization_id = NULL WHERE slug = 'kokonut-genesis'; UPDATE location SET organization_id = '{OTHER_ORG_ID}' WHERE slug = 'kokonut-seeds';",
        )
        failed_owner = seed(container, check=False)
        if failed_owner.returncode == 0 or "has a different organization assignment" not in failed_owner.stderr:
            raise RuntimeError("conflicting organization assignment did not fail closed")
        assert_value(
            container,
            "SELECT organization_id IS NULL FROM location WHERE slug = 'kokonut-genesis'",
            "t",
            "conflicting assignment rolls back prior location changes",
        )
        sql(
            container,
            f"UPDATE location SET organization_id = '{OWNER_ID}' WHERE slug = 'kokonut-genesis'; UPDATE location SET organization_id = NULL WHERE slug = 'kokonut-seeds';",
        )
        checks.append({"id": "conflicting_assignment_rollback", "result": "passed"})

        run(["docker", "rm", "--force", container])
        started = False
        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with networking disabled",
            "seed": str(SEED.relative_to(ROOT)),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "repository_secrets_read": False,
            "checks": checks,
        "aggregate_preflight_fields": [
            "expected_location_count",
            "present_exact_identity_count",
            "owner_confirmed_count",
            "missing_location_count",
            "identity_mismatch_count",
            "owner_mismatch_count",
        ],
            "cleanup": {"container_removed": True, "volume_retained": False},
            "scope_limit": "Synthetic records only; absent source locations are skipped, and this check does not backfill any candidate or production database.",
        }
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep disposable failures compact.
        print(f"NETWORK LOCATION OWNER MAP DISPOSABLE CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
