#!/usr/bin/env python3
"""Exercise the repository checkpoint command and documented isolated restore procedure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMPOSE = ROOT / "docker-compose.kernel-recovery-fixture.yml"
RESTORE_COMPOSE = ROOT / "docker-compose.kernel-recovery.yml"
SOURCE_IMAGE = "sha256:b573e82124b3530c454ea6d5ae8aefce1fb7ee137467f66f75a5079f8569ee6b"
ROLE_PREREQUISITES = ROOT / "scripts/kernel-restore-role-prerequisites.sql"
CHECKPOINT_SCRIPT = ROOT / "scripts/kernel-checkpoint.sh"


class CheckFailure(RuntimeError):
    """A safe stage failure with a bounded SQL diagnostic, when available."""

    def __init__(self, message: str, diagnostic: str | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int = 60,
    cwd: Path = ROOT,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        diagnostic = next(
            (
                line.strip()[:240]
                for line in (result.stderr + "\n" + result.stdout).splitlines()
                if re.match(r"^(?:ERROR|FATAL|DETAIL|HINT):", line.strip())
            ),
            None,
        )
        raise CheckFailure("a disposable recovery command failed", diagnostic)
    return result.stdout.strip()


def compose(project: str, manifest: Path) -> list[str]:
    return [
        "docker", "compose", "--project-directory", str(ROOT), "--env-file", "/dev/null",
        "-p", project, "-f", str(manifest),
    ]


def ensure_project_unused(project: str) -> None:
    label = f"label=com.docker.compose.project={project}"
    commands = (
        ["docker", "ps", "-a", "--filter", label, "--format", "{{.ID}}"],
        ["docker", "volume", "ls", "--filter", label, "--format", "{{.Name}}"],
        ["docker", "network", "ls", "--filter", label, "--format", "{{.ID}}"],
    )
    if any(run(command) for command in commands):
        raise CheckFailure("a unique disposable Compose project already has resources")
    containers = run(["docker", "ps", "-a", "--format", "{{.Names}}"])
    volumes = run(["docker", "volume", "ls", "--format", "{{.Name}}"])
    if f"{project}-database-1" in containers.splitlines() or any(
        name.startswith(f"{project}_") for name in volumes.splitlines()
    ):
        raise CheckFailure("a disposable resource name already exists")


def query(command: list[str], database: str, sql: str, env: dict[str, str]) -> str:
    return run(
        command + [
            "exec", "-T", "database", "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
            "-U", "kokonut", "-d", database,
        ],
        env=env,
        input_text=sql,
    )


def migration_fingerprint(output: str) -> dict[str, object]:
    parts = output.strip().split("|")
    if len(parts) != 3:
        raise CheckFailure("migration fingerprint query returned an invalid result")
    return {"applied": int(parts[0]), "migration_digest_md5": parts[1], "latest": parts[2]}


def restore_archive(
    command: list[str],
    project_env: dict[str, str],
    archive: Path,
    identity: Path,
) -> None:
    decrypt = subprocess.Popen(
        ["age", "-d", "-i", str(identity), str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decrypt.stdout is not None
    restore = subprocess.Popen(
        command
        + [
            "exec", "-T", "database", "pg_restore", "-U", "kokonut",
            "-d", "kokonut_restore", "--exit-on-error", "--single-transaction",
            "--no-owner", "--no-privileges",
        ],
        env=project_env,
        stdin=decrypt.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    decrypt.stdout.close()
    _, restore_stderr = restore.communicate(timeout=3600)
    _, decrypt_stderr = decrypt.communicate(timeout=3600)
    if restore.returncode or decrypt.returncode:
        diagnostic_lines = []
        for raw_line in (restore_stderr + b"\n" + decrypt_stderr).decode(
            "utf-8", errors="replace"
        ).splitlines():
            line = raw_line.strip()
            if not re.match(r"^(?:pg_restore:|ERROR:|FATAL:|DETAIL:|age: error:)", line):
                continue
            line = line.replace(os.fspath(archive.parent), "[checkpoint]")
            line = line.replace(os.fspath(identity), "[age identity]")
            diagnostic_lines.append(line[:240])
            if len(diagnostic_lines) == 4:
                break
        diagnostic = " | ".join(diagnostic_lines) or None
        raise CheckFailure("encrypted checkpoint restore failed", diagnostic)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--identity-file",
        type=Path,
        default=Path(os.environ.get("SOPS_AGE_KEY_FILE", Path.home() / ".config/sops/age/keys.txt")),
        help="local age identity used for encryption/decryption; contents are never displayed",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/refactor/builds/2026-10-27-recovery/kernel-checkpoint-restore-disposable.json",
    )
    args = parser.parse_args()
    if not args.identity_file.is_file():
        parser.error("age identity file does not exist")

    token = uuid.uuid4().hex[:8]
    source_project = f"kokonut-kernel-recovery-fixture-{token}"
    restore_project = f"kokonut-kernel-full-restore-{token}"
    source_container = f"{source_project}-database-1"
    temporary_dir: str | None = None
    started: set[str] = set()
    evidence: dict[str, object] = {
        "result": "failed",
        "candidate_or_legacy_touched": False,
        "seeds_applied": 0,
        "farm_data_loaded": False,
        "source_network": "internal; no host port",
        "restore_network": "internal; no host port",
        "plaintext_dump_written_to_disk": False,
        "age_identity_path_recorded": False,
        "cleanup": {"attempted": False, "completed": False},
        "limitations": [
            "Synthetic sentinel only; no populated farm records or external media/provider state is represented.",
            "Database-only checkpoint excludes cluster roles and external volumes; the documented role prerequisites are applied separately.",
            "This is a bounded restore rehearsal, not production RPO/RTO, R2, multi-provider, or 24-hour recovery acceptance.",
        ],
    }
    source_started = False
    restore_started = False
    stage = "preflight"
    try:
        if not SOURCE_COMPOSE.is_file() or not RESTORE_COMPOSE.is_file() or not ROLE_PREREQUISITES.is_file():
            raise CheckFailure("a recovery manifest or role-prerequisite file is unavailable")
        ensure_project_unused(source_project)
        ensure_project_unused(restore_project)
        image_result = run(
            ["docker", "image", "inspect", SOURCE_IMAGE, "--format", "{{.Os}}/{{.Architecture}} {{.Id}}"]
        ).split()
        if len(image_result) != 2 or image_result[0] != "linux/amd64":
            raise CheckFailure("the pinned recovery fixture image is not linux/amd64")
        evidence["image"] = {"platform": image_result[0], "image_id": image_result[1]}

        recipient_result = subprocess.run(
            ["age-keygen", "-y", str(args.identity_file)],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        recipient = recipient_result.stdout.strip()
        if recipient_result.returncode or not re.fullmatch(r"age1[0-9a-z]{20,}", recipient):
            raise CheckFailure("age identity could not produce a valid encryption recipient")

        temporary_dir = tempfile.mkdtemp(prefix="kokonut-full-recovery-")
        os.chmod(temporary_dir, 0o700)
        checkpoint = Path(temporary_dir) / "checkpoint"
        archive = checkpoint / "postgres.dump.age"

        source_env = os.environ.copy()
        source_env.update({
            "POSTGRES_PASSWORD": uuid.uuid4().hex + uuid.uuid4().hex,
            "KOKONUT_ENV": "development",
            "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
            "PG_DB": "kokonut_intelligence",
            "PG_USER": "kokonut",
        })
        source_command = compose(source_project, SOURCE_COMPOSE)
        stage = "source_start"
        source_started = True
        run(source_command + ["up", "-d", "--wait", "database"], env=source_env, timeout=240)
        migrations_command = [
            os.fspath(ROOT / ".venv/bin/python3") if (ROOT / ".venv/bin/python3").is_file() else "python3",
            "-m", "services.migration", "migrate", "--schemas-only",
            "--compose-project", source_project, "--compose-file", os.fspath(SOURCE_COMPOSE),
        ]
        stage = "current_schema_replay"
        run(migrations_command, env=source_env, timeout=3600)
        source_fingerprint = migration_fingerprint(
            query(
                source_command,
                "kokonut_intelligence",
                "SELECT count(*) FILTER (WHERE status='applied')::text || '|' || "
                "md5(string_agg(migration_id || ':' || checksum, E'\\n' ORDER BY migration_id)) || '|' || "
                "max(migration_id) FILTER (WHERE status='applied') "
                "FROM schema_migration WHERE migration_id LIKE 'schema:%' AND status='applied';",
                source_env,
            )
        )
        if source_fingerprint["applied"] != 643 or source_fingerprint["latest"] != "schema:652_runtime_append_only_data_access_log.sql":
            raise CheckFailure("source schema replay did not reach the expected 643-migration head")
        query(
            source_command,
            "kokonut_intelligence",
            "CREATE TABLE public.kernel_checkpoint_sentinel (id integer PRIMARY KEY, marker text NOT NULL);"
            "INSERT INTO public.kernel_checkpoint_sentinel VALUES (17, 'synthetic-restore-proof');",
            source_env,
        )
        evidence["source_schema"] = source_fingerprint
        evidence["source_container"] = source_container

        stage = "checkpoint"
        run(
            ["bash", os.fspath(CHECKPOINT_SCRIPT), source_container, os.fspath(checkpoint), recipient],
            env={**source_env, "KOKONUT_RECOVERY_FIXTURE_PROJECT": source_project},
            timeout=600,
        )
        manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
        archive_bytes = archive.read_bytes()
        digest = hashlib.sha256(archive_bytes).hexdigest()
        if manifest.get("sha256") != digest or not archive_bytes.startswith(b"age-encryption.org/v1\n"):
            raise CheckFailure("checkpoint manifest or age archive validation failed")
        if manifest.get("restore_rehearsed") is not False or manifest.get("database") != "kokonut_intelligence":
            raise CheckFailure("checkpoint manifest contains unexpected scope")
        evidence["checkpoint"] = {
            "bytes": len(archive_bytes),
            "sha256": digest,
            "age_encrypted": True,
            "manifest_sha256_matches": True,
            "scope": manifest.get("scope"),
        }

        restore_env = os.environ.copy()
        restore_env.update({
            "POSTGRES_PASSWORD": source_env["POSTGRES_PASSWORD"],
            "KOKONUT_RECOVERY_DATABASE_IMAGE": manifest["database_image"],
        })
        restore_command = compose(restore_project, RESTORE_COMPOSE)
        stage = "restore_target_start"
        restore_started = True
        run(restore_command + ["up", "-d", "--wait", "database"], env=restore_env, timeout=240)
        run(
            restore_command + [
                "exec", "-T", "database", "psql", "-v", "ON_ERROR_STOP=1",
                "-U", "kokonut", "-d", "postgres",
            ],
            env=restore_env,
            input_text=ROLE_PREREQUISITES.read_text(encoding="utf-8"),
        )
        run(
            restore_command + ["exec", "-T", "database", "createdb", "-U", "kokonut", "-T", "template0", "kokonut_restore"],
            env=restore_env,
        )
        stage = "restore_archive"
        restore_archive(restore_command, restore_env, archive, args.identity_file)
        stage = "restore_verify"
        restored_fingerprint = migration_fingerprint(
            query(
                restore_command,
                "kokonut_restore",
                "SELECT count(*) FILTER (WHERE status='applied')::text || '|' || "
                "md5(string_agg(migration_id || ':' || checksum, E'\\n' ORDER BY migration_id)) || '|' || "
                "max(migration_id) FILTER (WHERE status='applied') "
                "FROM schema_migration WHERE migration_id LIKE 'schema:%' AND status='applied';",
                restore_env,
            )
        )
        restored_sentinel = query(
            restore_command,
            "kokonut_restore",
            "SELECT id || ':' || marker FROM public.kernel_checkpoint_sentinel;",
            restore_env,
        )
        if restored_fingerprint != source_fingerprint or restored_sentinel != "17:synthetic-restore-proof":
            raise CheckFailure("restored schema fingerprint or synthetic sentinel did not match")
        evidence["restore"] = {
            "database": "fresh template0-derived kokonut_restore",
            "role_prerequisites_applied": True,
            "schema_fingerprint_matches": True,
            "migration_count": restored_fingerprint["applied"],
            "latest_migration": restored_fingerprint["latest"],
            "synthetic_sentinel_matches": True,
        }
        evidence["result"] = "passed"
    except (CheckFailure, OSError, subprocess.TimeoutExpired, KeyError, ValueError) as exc:
        evidence["failed_stage"] = stage
        evidence["failure"] = type(exc).__name__
        if isinstance(exc, CheckFailure) and exc.diagnostic:
            evidence["safe_diagnostic"] = exc.diagnostic
    finally:
        evidence["cleanup"] = {"attempted": True, "completed": True}
        for project, manifest, started in (
            (restore_project, RESTORE_COMPOSE, restore_started),
            (source_project, SOURCE_COMPOSE, source_started),
        ):
            if not started:
                continue
            result = subprocess.run(
                compose(project, manifest) + ["down", "--volumes", "--remove-orphans"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=300,
                env=source_env if project == source_project else restore_env,
            )
            if result.returncode:
                evidence["cleanup"]["completed"] = False
        if temporary_dir is not None:
            shutil.rmtree(temporary_dir, ignore_errors=True)
            if Path(temporary_dir).exists():
                evidence["cleanup"]["completed"] = False
        output = args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(output)
    return 0 if evidence["result"] == "passed" and evidence["cleanup"]["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
