#!/usr/bin/env python3
"""Apply migration 401 and verify hold-aware cleanup on isolated PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_ID = "schema:401_dynamic_retention_and_legal_holds.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-15-recovery/retention-policy-disposable.json"


def run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{details}")
    return result.stdout.strip()


def compose_args(project: str, compose_file: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "--env-file",
        "/dev/null",
        "-p",
        project,
        "-f",
        str(compose_file),
    ]


def psql(compose: list[str], statement: str) -> str:
    return run(
        [
            *compose,
            "exec",
            "-T",
            "database",
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "kokonut",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def pre_migration_fixture() -> str:
    return """
CREATE TABLE data_retention_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_category VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    location_id UUID,
    retention_days INTEGER NOT NULL DEFAULT 2555,
    deletion_method VARCHAR(50) NOT NULL DEFAULT 'soft_delete',
    archive_after_days INTEGER,
    anonymize_fields TEXT[],
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    legal_hold_reason TEXT,
    override_reason TEXT,
    auto_enforce BOOLEAN NOT NULL DEFAULT TRUE,
    last_enforced_at TIMESTAMPTZ,
    enforcement_status VARCHAR(20) NOT NULL DEFAULT 'active',
    policy_owner VARCHAR(200),
    approved_by VARCHAR(200),
    approval_date DATE,
    document_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    priority INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE data_governance_category (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    default_retention_days INTEGER NOT NULL DEFAULT 2555
);
CREATE TABLE consent_data_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    default_retention_days INTEGER DEFAULT 365
);
CREATE TABLE data_retention_enforcement_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES data_retention_policy(id),
    actor VARCHAR(200) NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL,
    candidates INTEGER NOT NULL DEFAULT 0,
    affected INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE retention_fixture (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ
);
CREATE TABLE platform_event (
    id UUID PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE event_dead_letter (
    original_event_id UUID NOT NULL,
    disposition VARCHAR(20) NOT NULL DEFAULT 'pending'
);
CREATE TABLE event_handler_delivery (
    event_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL
);
INSERT INTO data_governance_category (category_key, display_name)
VALUES ('fixture', 'Fixture');
INSERT INTO consent_data_type (name) VALUES ('fixture');
INSERT INTO data_retention_policy
    (id, data_category, entity_type, retention_days, deletion_method,
     auto_enforce, status)
VALUES
    ('a0000000-0000-0000-0000-000000000401', 'legacy_fixture',
     'legacy_fixture', 30, 'soft_delete', TRUE, 'active'),
    ('a0000000-0000-0000-0000-000000000402', 'approved_fixture',
     'approved_fixture', 99, 'soft_delete', TRUE, 'active');
UPDATE data_retention_policy
SET approved_by = 'reviewer', approval_date = CURRENT_DATE,
    policy_owner = 'owner'
WHERE id = 'a0000000-0000-0000-0000-000000000402';
"""


def acceptance_sql() -> str:
    return """
DO $$
DECLARE
    legacy_status TEXT;
    legacy_auto BOOLEAN;
    approved_status TEXT;
    approved_auto BOOLEAN;
    candidate_count INTEGER;
    removed_count INTEGER;
    policy_count INTEGER;
    retention_window INTEGER;
BEGIN
    SELECT status, auto_enforce INTO legacy_status, legacy_auto
    FROM data_retention_policy
    WHERE id = 'a0000000-0000-0000-0000-000000000401';
    IF legacy_status <> 'draft' OR legacy_auto IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'unapproved legacy policy was not made inert';
    END IF;
    SELECT status, auto_enforce INTO approved_status, approved_auto
    FROM data_retention_policy
    WHERE id = 'a0000000-0000-0000-0000-000000000402';
    IF approved_status <> 'active' OR approved_auto IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'explicitly approved policy was not preserved';
    END IF;
    IF (SELECT default_retention_days FROM data_governance_category
        WHERE category_key = 'fixture') IS NOT NULL
       OR (SELECT default_retention_days FROM consent_data_type
        WHERE name = 'fixture') IS NOT NULL THEN
        RAISE EXCEPTION 'reference-category retention defaults were not cleared';
    END IF;
    IF (SELECT action FROM data_retention_policy_event
        WHERE policy_id = 'a0000000-0000-0000-0000-000000000401')
        <> 'migration_review_required' THEN
        RAISE EXCEPTION 'legacy policy review event was not recorded';
    END IF;
    IF (SELECT character_maximum_length FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'data_retention_policy_event'
          AND column_name = 'action') < length('migration_review_required') THEN
        RAISE EXCEPTION 'policy action column cannot store migration review action';
    END IF;
END;
$$;

INSERT INTO retention_fixture (id, created_at) VALUES
    ('a0000000-0000-0000-0000-000000000411', NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000412', NOW() - INTERVAL '10 days');
INSERT INTO data_retention_policy
    (id, data_category, entity_type, retention_days, deletion_method,
     auto_enforce, enforcement_status, policy_owner, approved_by,
     approval_date, status)
VALUES ('a0000000-0000-0000-0000-000000000413', 'retention_fixture',
        'retention_fixture', 1, 'soft_delete', TRUE, 'active',
        'fixture-owner', 'fixture-reviewer', CURRENT_DATE, 'active');
INSERT INTO data_retention_legal_hold
    (id, entity_type, entity_id, reason, placed_by)
VALUES ('a0000000-0000-0000-0000-000000000414', 'retention_fixture',
        'a0000000-0000-0000-0000-000000000411', 'preserve during review',
        'fixture-operator');
DO $$
DECLARE candidate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO candidate_count
    FROM retention_fixture entity
    WHERE created_at < NOW() - make_interval(days => 1)
      AND NOT EXISTS (
          SELECT 1 FROM data_retention_legal_hold hold
          WHERE hold.entity_type = 'retention_fixture'
            AND hold.entity_id = entity.id AND hold.released_at IS NULL
      );
    IF candidate_count <> 1 THEN
        RAISE EXCEPTION 'generic retention candidate query did not exclude active hold';
    END IF;
END;
$$;
DO $$
BEGIN
    BEGIN
        INSERT INTO data_retention_legal_hold
            (entity_type, entity_id, reason, placed_by)
        VALUES ('retention_fixture', 'a0000000-0000-0000-0000-000000000411',
                'duplicate active hold', 'fixture-operator');
        RAISE EXCEPTION 'duplicate active hold was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END;
$$;
UPDATE data_retention_legal_hold
SET released_by = 'fixture-reviewer', released_at = NOW(),
    release_reason = 'review completed'
WHERE id = 'a0000000-0000-0000-0000-000000000414';
DO $$
DECLARE candidate_count INTEGER;
BEGIN
    IF (SELECT array_agg(action ORDER BY action)
        FROM data_retention_legal_hold_event
        WHERE hold_id = 'a0000000-0000-0000-0000-000000000414')
       IS DISTINCT FROM ARRAY['placed', 'released']::VARCHAR[] THEN
        RAISE EXCEPTION 'hold placement/release history is incomplete';
    END IF;
    SELECT COUNT(*) INTO candidate_count
    FROM retention_fixture entity
    WHERE created_at < NOW() - make_interval(days => 1)
      AND NOT EXISTS (
          SELECT 1 FROM data_retention_legal_hold hold
          WHERE hold.entity_type = 'retention_fixture'
            AND hold.entity_id = entity.id AND hold.released_at IS NULL
      );
    IF candidate_count <> 2 THEN
        RAISE EXCEPTION 'released hold still excludes generic retention candidate';
    END IF;
END;
$$;
DO $$
BEGIN
    BEGIN
        UPDATE data_retention_legal_hold_event
        SET reason = 'tampered'
        WHERE hold_id = 'a0000000-0000-0000-0000-000000000414';
        RAISE EXCEPTION 'legal-hold event mutation was accepted';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'retention legal hold history is append-only' THEN
            RAISE;
        END IF;
    END;
END;
$$;

INSERT INTO data_retention_policy
    (id, data_category, entity_type, retention_days, deletion_method,
     auto_enforce, enforcement_status, policy_owner, approved_by,
     approval_date, status)
VALUES ('a0000000-0000-0000-0000-000000000421', 'event_bus',
        'platform_event', 1, 'hard_delete', TRUE, 'active',
        'fixture-owner', 'fixture-reviewer', CURRENT_DATE, 'active');
INSERT INTO platform_event (id, status, created_at) VALUES
    ('a0000000-0000-0000-0000-000000000431', 'completed', NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000432', 'completed', NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000433', 'completed', NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000434', 'completed', NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000435', 'processing', NOW() - INTERVAL '10 days');
INSERT INTO event_dead_letter (original_event_id, disposition)
VALUES ('a0000000-0000-0000-0000-000000000433', 'pending');
INSERT INTO event_handler_delivery (event_id, status)
VALUES ('a0000000-0000-0000-0000-000000000434', 'error');
INSERT INTO data_retention_legal_hold
    (id, entity_type, entity_id, reason, placed_by)
VALUES ('a0000000-0000-0000-0000-000000000436', 'platform_event',
        'a0000000-0000-0000-0000-000000000432', 'preserve event',
        'fixture-operator');
DO $$
DECLARE
    policy_count INTEGER;
    retention_window INTEGER;
BEGIN
    SELECT COUNT(*), MIN(retention_days)
    INTO policy_count, retention_window
    FROM data_retention_policy
    WHERE data_category = 'event_bus'
      AND entity_type = 'platform_event'
      AND location_id IS NULL
      AND retention_days > 0
      AND deletion_method = 'hard_delete'
      AND legal_hold = FALSE
      AND auto_enforce = TRUE
      AND enforcement_status = 'active'
      AND NULLIF(BTRIM(approved_by), '') IS NOT NULL
      AND NULLIF(BTRIM(policy_owner), '') IS NOT NULL
      AND approval_date IS NOT NULL
      AND status = 'active';
    IF policy_count <> 1 OR retention_window <> 1 THEN
        RAISE EXCEPTION 'approved global event policy was not uniquely selected';
    END IF;
END;
$$;
DO $$
DECLARE removed_count INTEGER;
BEGIN
    WITH removed AS (
        DELETE FROM platform_event
        WHERE created_at < NOW() - make_interval(days => 1)
          AND status IN ('completed', 'dead_letter')
          AND NOT EXISTS (
              SELECT 1 FROM event_dead_letter dead
              WHERE dead.original_event_id = platform_event.id
                AND dead.disposition = 'pending'
          )
          AND NOT EXISTS (
              SELECT 1 FROM event_handler_delivery delivery
              WHERE delivery.event_id = platform_event.id
                AND delivery.status <> 'success'
          )
          AND NOT EXISTS (
              SELECT 1 FROM data_retention_legal_hold hold
              WHERE hold.entity_type = 'platform_event'
                AND hold.entity_id = platform_event.id
                AND hold.released_at IS NULL
          )
        RETURNING id
    )
    SELECT COUNT(*) INTO removed_count FROM removed;
    IF removed_count <> 1 THEN
        RAISE EXCEPTION 'event cleanup did not delete only unheld completed event';
    END IF;
END;
$$;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM platform_event
        WHERE id = 'a0000000-0000-0000-0000-000000000431')
       OR (SELECT COUNT(*) FROM platform_event
        WHERE id IN ('a0000000-0000-0000-0000-000000000432',
                     'a0000000-0000-0000-0000-000000000433',
                     'a0000000-0000-0000-0000-000000000434',
                     'a0000000-0000-0000-0000-000000000435')) <> 4 THEN
        RAISE EXCEPTION 'event cleanup violated hold, dead-letter, delivery, or active-state guard';
    END IF;
END;
$$;
UPDATE data_retention_legal_hold
SET released_by = 'fixture-reviewer', released_at = NOW(),
    release_reason = 'event review completed'
WHERE id = 'a0000000-0000-0000-0000-000000000436';
UPDATE event_dead_letter SET disposition = 'resolved'
WHERE original_event_id = 'a0000000-0000-0000-0000-000000000433';
UPDATE event_handler_delivery SET status = 'success'
WHERE event_id = 'a0000000-0000-0000-0000-000000000434';
DO $$
DECLARE removed_count INTEGER;
BEGIN
    WITH removed AS (
        DELETE FROM platform_event
        WHERE created_at < NOW() - make_interval(days => 1)
          AND status IN ('completed', 'dead_letter')
          AND NOT EXISTS (
              SELECT 1 FROM event_dead_letter dead
              WHERE dead.original_event_id = platform_event.id
                AND dead.disposition = 'pending'
          )
          AND NOT EXISTS (
              SELECT 1 FROM event_handler_delivery delivery
              WHERE delivery.event_id = platform_event.id
                AND delivery.status <> 'success'
          )
          AND NOT EXISTS (
              SELECT 1 FROM data_retention_legal_hold hold
              WHERE hold.entity_type = 'platform_event'
                AND hold.entity_id = platform_event.id
                AND hold.released_at IS NULL
          )
        RETURNING id
    )
    SELECT COUNT(*) INTO removed_count FROM removed;
    IF removed_count <> 3 THEN
        RAISE EXCEPTION 'released/resolved completed events were not cleaned up';
    END IF;
    IF (SELECT array_agg(id ORDER BY id) FROM platform_event)
       IS DISTINCT FROM ARRAY['a0000000-0000-0000-0000-000000000435'::uuid] THEN
        RAISE EXCEPTION 'pending event was pruned';
    END IF;
END;
$$;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    compose_source = (ROOT / "docker-compose.yml").read_text()
    image_match = re.search(r"(?m)^\s*image:\s*(postgis/postgis:[^\s]+)\s*$", compose_source)
    if image_match is None:
        raise RuntimeError("could not find pinned PostGIS image in docker-compose.yml")
    image = image_match.group(1)
    project = f"kokonut-retention-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(24)
    result = {
        "date": "2026-10-15",
        "kind": "disposable-postgresql-migration-and-retention-acceptance",
        "migration_id": MIGRATION_ID,
        "docker_image": image,
        "network": "internal-only; no host ports published",
        "checks": [],
        "candidate_or_legacy_database_touched": False,
        "retention_cleanup_enabled_in_repository": False,
    }

    with tempfile.TemporaryDirectory(prefix="kokonut-retention-") as temp_dir:
        compose_file = Path(temp_dir) / "compose.yml"
        compose_file.write_text(
            "services:\n"
            "  database:\n"
            f"    image: {image}\n"
            "    environment:\n"
            "      POSTGRES_DB: postgres\n"
            "      POSTGRES_USER: kokonut\n"
            f"      POSTGRES_PASSWORD: {json.dumps(password)}\n"
            "    healthcheck:\n"
            "      test: [CMD-SHELL, pg_isready -U kokonut -d postgres]\n"
            "      interval: 1s\n"
            "      timeout: 3s\n"
            "      retries: 30\n"
            "networks:\n"
            "  default:\n"
            "    internal: true\n"
        )
        compose = compose_args(project, compose_file)
        try:
            run([*compose, "up", "--pull", "never", "-d", "--wait", "database"])
            psql(compose, pre_migration_fixture())
            env = os.environ.copy()
            env.update(
                {
                    "PGHOST": "127.0.0.1",
                    "PGPORT": "5432",
                    "PGUSER": "kokonut",
                    "PGPASSWORD": password,
                    "PG_DB": "postgres",
                    "KOKONUT_ENV": "development",
                    "KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT": "true",
                }
            )
            migration = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "services.migration",
                    "migrate",
                    "--schemas-only",
                    "--compose-project",
                    project,
                    "--compose-file",
                    str(compose_file),
                    "--only-migration",
                    MIGRATION_ID,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if migration.returncode:
                details = "\n".join(part for part in (migration.stdout, migration.stderr) if part)
                raise RuntimeError(f"ordered migration runner failed:\n{details}")
            result["checks"] = [
                "ordered migration runner applied migration 401 to a synthetic pre-migration fixture",
                "legacy policies lacking approval were demoted; explicit approvals and dynamic default removal verified",
                "legal-hold placement/release audit, active-hold uniqueness, and append-only history verified",
                "generic retention candidate selection excludes active holds and resumes after release",
                "event cleanup selects one approved window and preserves legal holds, pending dead letters, unsuccessful deliveries, and processing events",
            ]
            psql(compose, acceptance_sql())
            result["migration_runner_output"] = migration.stdout.strip().splitlines()[-1]
            result["result"] = "passed"
        except Exception as exc:
            logs = subprocess.run(
                [*compose, "logs", "--no-color", "database"],
                text=True,
                capture_output=True,
                check=False,
            )
            details = "\n".join(part for part in (logs.stdout, logs.stderr) if part)
            if details:
                raise RuntimeError(f"{exc}\nDisposable PostgreSQL logs:\n{details}") from exc
            raise
        finally:
            subprocess.run(
                [*compose, "down", "--volumes", "--remove-orphans"],
                text=True,
                capture_output=True,
                check=False,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
