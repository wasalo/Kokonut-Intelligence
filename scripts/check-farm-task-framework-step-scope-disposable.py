#!/usr/bin/env python3
"""Exercise migration 698 location-scope constraints on disposable PostgreSQL."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_IMAGE = (
    "postgis/postgis:16-3.4@sha256:"
    "44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)
ARM64_IMAGE = "kokonut-kernel-postgis-arm64:local"
MIGRATION = ROOT / "schemas/postgres/698_farm_task_framework_step_location_scope.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-30-recovery/"

LOCATION_A = "00000000-0000-0000-0000-000000000001"
LOCATION_B = "00000000-0000-0000-0000-000000000002"
TASK_MATCHED = "00000000-0000-0000-0000-000000000011"
TASK_UNRESOLVED = "00000000-0000-0000-0000-000000000012"
TASK_TRANSFER = "00000000-0000-0000-0000-000000000013"
STEP_MATCHED = "00000000-0000-0000-0000-000000000021"
STEP_OTHER_LOCATION = "00000000-0000-0000-0000-000000000022"
STEP_TRANSFER = "00000000-0000-0000-0000-000000000023"


def run(command: list[str], *, input_text: str | None = None, timeout: int = 90):
    return subprocess.run(
        command,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def psql(container: str, sql_text: str, *, expect_success: bool = True) -> str:
    result = run(
        [
            "docker", "exec", "-i", container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=sql_text,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if expect_success and result.returncode != 0:
        raise RuntimeError(f"disposable SQL failed: {output[-2000:]}")
    if not expect_success and result.returncode == 0:
        raise AssertionError("expected disposable SQL to be rejected")
    return output


def run_checks(platform: str, image: str) -> dict[str, object]:
    container = f"kokonut-farm-task-scope-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(24)
    start = time.monotonic()
    created = False
    result: dict[str, object] = {
        "result": "failed",
        "platform": platform,
        "image": image,
        "network_mode": "none",
        "host_ports_published": False,
        "candidate_legacy_or_production_touched": False,
        "farm_data_loaded": False,
    }
    try:
        command = [
            "docker", "run", "--detach", "--rm", "--name", container,
            "--network", "none", "--env", f"POSTGRES_PASSWORD={password}",
        ]
        if platform:
            command.extend(("--platform", platform))
        command.append(image)
        started = run(command, timeout=120)
        if started.returncode != 0:
            raise RuntimeError("could not start isolated disposable PostgreSQL")
        created = True

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            logs = run(["docker", "logs", container], timeout=20)
            log_text = f"{logs.stdout}\n{logs.stderr}"
            if "PostgreSQL init process complete; ready for start up." not in log_text:
                time.sleep(0.5)
                continue
            ready = run(
                [
                    "docker", "exec", container,
                    "psql", "-X", "-U", "postgres", "-d", "postgres",
                    "-Atqc", "SELECT 1",
                ]
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        psql(
            container,
            f"""
            CREATE TABLE public.location (id UUID PRIMARY KEY);
            CREATE TABLE public.farm_task (
                id UUID PRIMARY KEY,
                location_id UUID NOT NULL REFERENCES public.location(id)
            );
            CREATE TABLE public.framework_step (
                id UUID PRIMARY KEY,
                location_id UUID NOT NULL REFERENCES public.location(id)
            );
            CREATE TABLE public.farm_task_framework_step (
                task_id UUID NOT NULL REFERENCES public.farm_task(id) ON DELETE CASCADE,
                framework_step_id UUID NOT NULL REFERENCES public.framework_step(id) ON DELETE CASCADE,
                source_system TEXT,
                PRIMARY KEY (task_id, framework_step_id)
            );
            INSERT INTO public.location VALUES ('{LOCATION_A}'), ('{LOCATION_B}');
            INSERT INTO public.farm_task VALUES
                ('{TASK_MATCHED}', '{LOCATION_A}'),
                ('{TASK_UNRESOLVED}', '{LOCATION_B}'),
                ('{TASK_TRANSFER}', '{LOCATION_A}');
            INSERT INTO public.framework_step VALUES
                ('{STEP_MATCHED}', '{LOCATION_A}'),
                ('{STEP_OTHER_LOCATION}', '{LOCATION_B}'),
                ('{STEP_TRANSFER}', '{LOCATION_A}');
            INSERT INTO public.farm_task_framework_step
                (task_id, framework_step_id, source_system)
            VALUES
                ('{TASK_MATCHED}', '{STEP_MATCHED}', 'synthetic-matched'),
                ('{TASK_UNRESOLVED}', '{STEP_MATCHED}', 'synthetic-unresolved');
            """,
        )

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(container, migration_sql)
        psql(container, migration_sql)

        psql(
            container,
            f"""
            DO $$
            DECLARE actual_location UUID;
            BEGIN
                SELECT location_id INTO actual_location
                  FROM public.farm_task_framework_step
                 WHERE task_id = '{TASK_MATCHED}';
                IF actual_location IS DISTINCT FROM '{LOCATION_A}'::uuid THEN
                    RAISE EXCEPTION 'same-location legacy edge was not safely backfilled';
                END IF;

                SELECT location_id INTO actual_location
                  FROM public.farm_task_framework_step
                 WHERE task_id = '{TASK_UNRESOLVED}';
                IF actual_location IS NOT NULL THEN
                    RAISE EXCEPTION 'cross-location legacy edge was guessed or rewritten';
                END IF;

                -- Existing importer shape omits location_id; trigger derives it.
                INSERT INTO public.farm_task_framework_step (task_id, framework_step_id)
                VALUES ('{TASK_TRANSFER}', '{STEP_TRANSFER}');
                SELECT location_id INTO actual_location
                  FROM public.farm_task_framework_step
                 WHERE task_id = '{TASK_TRANSFER}';
                IF actual_location IS DISTINCT FROM '{LOCATION_A}'::uuid THEN
                    RAISE EXCEPTION 'same-location insert did not derive its scope';
                END IF;

                BEGIN
                    INSERT INTO public.farm_task_framework_step (task_id, framework_step_id)
                    VALUES ('{TASK_MATCHED}', '{STEP_OTHER_LOCATION}');
                    RAISE EXCEPTION 'cross-location insert unexpectedly succeeded';
                EXCEPTION WHEN check_violation THEN
                    NULL;
                END;

                BEGIN
                    UPDATE public.farm_task_framework_step
                       SET source_system = 'attempted-edit'
                     WHERE task_id = '{TASK_UNRESOLVED}';
                    RAISE EXCEPTION 'unresolved historical edge was unexpectedly editable';
                EXCEPTION WHEN check_violation THEN
                    NULL;
                END;

                BEGIN
                    UPDATE public.farm_task
                       SET location_id = '{LOCATION_A}'
                     WHERE id = '{TASK_UNRESOLVED}';
                    RAISE EXCEPTION 'task with unresolved edge was unexpectedly moved';
                EXCEPTION WHEN check_violation THEN
                    NULL;
                END;
            END;
            $$;
            """,
        )

        # A scoped edge prevents moving one endpoint alone through its composite FK.
        psql(
            container,
            f"""
            BEGIN;
            SET CONSTRAINTS fk_farm_task_framework_step_task_location IMMEDIATE;
            UPDATE public.farm_task SET location_id = '{LOCATION_B}'
             WHERE id = '{TASK_TRANSFER}';
            COMMIT;
            """,
            expect_success=False,
        )
        psql(
            container,
            f"""
            DO $$
            BEGIN
                IF (SELECT location_id FROM public.farm_task WHERE id = '{TASK_TRANSFER}')
                   IS DISTINCT FROM '{LOCATION_A}'::uuid THEN
                    RAISE EXCEPTION 'failed single-endpoint move was not rolled back';
                END IF;
            END;
            $$;
            BEGIN;
            UPDATE public.farm_task SET location_id = '{LOCATION_B}'
             WHERE id = '{TASK_TRANSFER}';
            UPDATE public.framework_step SET location_id = '{LOCATION_B}'
             WHERE id = '{STEP_TRANSFER}';
            UPDATE public.farm_task_framework_step SET location_id = '{LOCATION_B}'
             WHERE task_id = '{TASK_TRANSFER}' AND framework_step_id = '{STEP_TRANSFER}';
            COMMIT;
            """,
        )

        result.update(
            {
                "result": "passed",
                "migration_applied_and_replayed": True,
                "matching_legacy_edge_backfilled": True,
                "unresolved_legacy_edge_preserved_null": True,
                "old_named_column_insert_shape_derives_location": True,
                "cross_location_insert_denied": True,
                "unresolved_legacy_edge_edit_denied": True,
                "unresolved_endpoint_move_denied": True,
                "single_endpoint_move_denied": True,
                "coordinated_same_scope_move_allowed": True,
                "synthetic_unresolved_edges": 1,
                "elapsed_seconds": round(time.monotonic() - start, 3),
            }
        )
        return result
    finally:
        if created:
            run(["docker", "rm", "--force", container], timeout=30)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"), default="linux/amd64")
    parser.add_argument("--image", help="override the disposable PostgreSQL image")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    image = args.image or (ARM64_IMAGE if args.platform == "linux/arm64" else NATIVE_IMAGE)
    output = args.output or (
        DEFAULT_OUTPUT
        / (
            "farm-task-framework-step-698-arm64-disposable.json"
            if args.platform == "linux/arm64"
            else "farm-task-framework-step-698-disposable.json"
        )
    )
    evidence = run_checks(args.platform, image)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.relative_to(ROOT))
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
