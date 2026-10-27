#!/usr/bin/env python3
"""Rehearse a synthetic, age-encrypted PostgreSQL dump/restore without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = (
    "postgis/postgis:16-3.4@sha256:"
    "44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)
OWNER_LABEL = "io.kokonut.disposable-check"


class CheckFailure(RuntimeError):
    """A safe stage-only failure; command output may contain local details."""


def run(command: list[str], *, input_text: str | None = None, timeout: int = 30) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        raise CheckFailure("a disposable recovery command failed")
    return result.stdout.strip()


def require_absent(kind: str, name: str) -> None:
    result = subprocess.run(
        ["docker", kind, "inspect", name], text=True, capture_output=True, check=False
    )
    if result.returncode == 0:
        raise CheckFailure("a randomly named disposable resource already exists")


def inspect_image() -> dict[str, str]:
    parts = run(
        ["docker", "image", "inspect", POSTGRES_IMAGE, "--format", "{{.Os}} {{.Architecture}} {{.Id}}"]
    ).split()
    if len(parts) != 3 or parts[:2] != ["linux", "amd64"]:
        raise CheckFailure("the pinned local PostgreSQL image is not linux/amd64")
    return {"platform": "linux/amd64", "image_id": parts[2]}


def owned_resource_exists(kind: str, name: str, run_id: str) -> bool:
    result = subprocess.run(
        ["docker", kind, "inspect", name], text=True, capture_output=True, check=False
    )
    if result.returncode:
        return False
    if kind == "container":
        labels = json.loads(
            run(["docker", "inspect", name, "--format", "{{json .Config.Labels}}"])
        )
    else:
        labels = json.loads(
            run(["docker", "volume", "inspect", name, "--format", "{{json .Labels}}"])
        )
    return isinstance(labels, dict) and labels.get(OWNER_LABEL) == run_id


def remove_owned(kind: str, name: str, run_id: str) -> bool:
    if not owned_resource_exists(kind, name, run_id):
        return True
    command = ["docker", "rm", "--force"] if kind == "container" else ["docker", "volume", "rm"]
    result = subprocess.run(command + [name], text=True, capture_output=True, check=False)
    return result.returncode == 0


def start_database(name: str, volume: str, run_id: str, password: str) -> None:
    run(
        [
            "docker", "volume", "create", "--label", f"{OWNER_LABEL}={run_id}", volume,
        ]
    )
    run(
        [
            "docker", "run", "--detach", "--name", name, "--pull=never",
            "--platform", "linux/amd64", "--network", "none",
            "--label", f"{OWNER_LABEL}={run_id}",
            "--mount", f"type=volume,src={volume},dst=/var/lib/postgresql/data",
            "--env", "POSTGRES_USER=kokonut", "--env", "POSTGRES_DB=postgres",
            "--env", f"POSTGRES_PASSWORD={password}", POSTGRES_IMAGE,
        ],
        timeout=90,
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        ready = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "kokonut", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if ready.returncode == 0:
            return
        time.sleep(1)
    raise CheckFailure("a disposable PostgreSQL container did not become ready")


def query(name: str, sql: str) -> str:
    output = run(
        ["docker", "exec", "-i", name, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "kokonut", "-d", "kokonut_recovery"],
        input_text=sql,
    )
    return output


def create_empty_restore_database(name: str) -> None:
    run(["docker", "exec", name, "createdb", "-U", "kokonut", "-T", "template0", "kokonut_recovery"])


def stream_encrypted_dump(source: str, archive: Path, recipient: str) -> None:
    dump = subprocess.Popen(
        ["docker", "exec", source, "pg_dump", "-U", "kokonut", "-d", "kokonut_recovery", "--format=custom", "--no-owner", "--no-privileges"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert dump.stdout is not None
    encrypt = subprocess.Popen(
        ["age", "-r", recipient, "-o", str(archive)],
        stdin=dump.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    dump.stdout.close()
    encrypt.communicate(timeout=120)
    dump.communicate(timeout=120)
    if dump.returncode or encrypt.returncode:
        raise CheckFailure("synthetic dump encryption failed")


def restore_encrypted_dump(target: str, archive: Path, identity: Path) -> None:
    decrypt = subprocess.Popen(
        ["age", "-d", "-i", str(identity), str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decrypt.stdout is not None
    restore = subprocess.Popen(
        [
            "docker", "exec", "-i", target, "pg_restore", "-U", "kokonut",
            "-d", "kokonut_recovery", "--exit-on-error", "--single-transaction",
            "--no-owner", "--no-privileges",
        ],
        stdin=decrypt.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    decrypt.stdout.close()
    restore.communicate(timeout=120)
    decrypt.communicate(timeout=120)
    if decrypt.returncode or restore.returncode:
        raise CheckFailure("encrypted synthetic database restore failed")


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
        default=ROOT / "docs/refactor/builds/2026-10-27-recovery/kernel-synthetic-backup-restore.json",
    )
    args = parser.parse_args()
    if not args.identity_file.is_file():
        parser.error("age identity file does not exist")

    output = args.output
    run_id = uuid.uuid4().hex
    source = f"kokonut-backup-source-{run_id[:12]}"
    target = f"kokonut-backup-restore-{run_id[:12]}"
    source_volume = f"kokonut-backup-source-data-{run_id[:12]}"
    target_volume = f"kokonut-backup-restore-data-{run_id[:12]}"
    resources = (
        ("volume", source_volume),
        ("container", source),
        ("volume", target_volume),
        ("container", target),
    )
    evidence: dict[str, object] = {
        "result": "failed",
        "source": "synthetic PostgreSQL database only",
        "candidate_or_legacy_touched": False,
        "network_mode": "none",
        "host_ports_published": False,
        "plaintext_dump_written_to_disk": False,
        "age_identity_path_recorded": False,
        "cleanup": {"attempted": False, "completed": False},
        "limitations": [
            "Synthetic database only; no application schemas, cluster roles, external providers, media, or farm records are covered.",
            "Checks the streaming pg_dump/age/pg_restore primitives, not scripts/kernel-checkpoint.sh, the full role-bootstrap restore procedure, or whole-platform recovery.",
            "This does not establish R2 transfer, production credential custody, retention, or a coordinated multi-provider checkpoint.",
        ],
    }
    created: set[tuple[str, str]] = set()
    stage = "preflight"
    temporary: str | None = None
    try:
        for kind, name in resources:
            require_absent(kind, name)
        image = inspect_image()
        evidence["image"] = {"reference": POSTGRES_IMAGE, **image}
        recipient_result = subprocess.run(
            ["age-keygen", "-y", str(args.identity_file)],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        recipient = recipient_result.stdout.strip()
        if recipient_result.returncode or not re.fullmatch(r"age1[0-9a-z]{20,}", recipient):
            raise CheckFailure("age identity could not produce a valid recipient")

        temporary = tempfile.mkdtemp(prefix="kokonut-synthetic-recovery-")
        os.chmod(temporary, 0o700)
        archive = Path(temporary) / "database.dump.age"
        password = secrets.token_urlsafe(32)
        stage = "source_start"
        created.update({("volume", source_volume), ("container", source)})
        start_database(source, source_volume, run_id, password)
        create_empty_restore_database(source)
        host_config = json.loads(run(["docker", "inspect", source, "--format", "{{json .HostConfig}}" ]))
        if host_config.get("NetworkMode") != "none" or host_config.get("PortBindings") or host_config.get("Privileged"):
            raise CheckFailure("source container isolation did not match the disposable policy")

        stage = "synthetic_source"
        query(
            source,
            "CREATE TABLE public.kernel_checkpoint_sentinel (id integer PRIMARY KEY, marker text NOT NULL);"
            "INSERT INTO public.kernel_checkpoint_sentinel VALUES (1, 'synthetic-alpha'), (2, 'synthetic-βeta');",
        )
        expected = "1:synthetic-alpha\n2:synthetic-βeta"
        if query(source, "SELECT id || ':' || marker FROM public.kernel_checkpoint_sentinel ORDER BY id;") != expected:
            raise CheckFailure("synthetic source rows did not match the fixture")

        stage = "encrypted_backup"
        stream_encrypted_dump(source, archive, recipient)
        archive_bytes = archive.read_bytes()
        if not archive_bytes.startswith(b"age-encryption.org/v1\n"):
            raise CheckFailure("checkpoint is not an age-encrypted archive")
        digest = hashlib.sha256(archive_bytes).hexdigest()
        evidence["checkpoint"] = {
            "bytes": len(archive_bytes),
            "sha256": digest,
            "age_encrypted": True,
            "plaintext_dump_on_disk": False,
        }

        # A fresh identity must not decrypt the archive; the diagnostic is suppressed.
        wrong_identity = Path(temporary) / "wrong-age-identity.txt"
        generated = subprocess.run(
            ["age-keygen", "-o", str(wrong_identity)],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if generated.returncode:
            raise CheckFailure("could not create a temporary negative-control identity")
        os.chmod(wrong_identity, 0o600)
        wrong_decrypt = subprocess.run(
            ["age", "-d", "-i", str(wrong_identity), str(archive)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
        if wrong_decrypt.returncode == 0:
            raise CheckFailure("wrong age identity unexpectedly decrypted the archive")

        stage = "restore_target_start"
        created.update({("volume", target_volume), ("container", target)})
        start_database(target, target_volume, run_id, password)
        create_empty_restore_database(target)
        target_config = json.loads(run(["docker", "inspect", target, "--format", "{{json .HostConfig}}" ]))
        if target_config.get("NetworkMode") != "none" or target_config.get("PortBindings") or target_config.get("Privileged"):
            raise CheckFailure("restore container isolation did not match the disposable policy")

        stage = "restore"
        restore_encrypted_dump(target, archive, args.identity_file)
        restored = query(target, "SELECT id || ':' || marker FROM public.kernel_checkpoint_sentinel ORDER BY id;")
        if restored != expected:
            raise CheckFailure("restored synthetic rows did not match the source")
        evidence["round_trip"] = {
            "source_rows": 2,
            "restored_rows": 2,
            "contents_match": True,
            "wrong_identity_rejected": True,
            "restored_to_fresh_database": True,
        }
        evidence["result"] = "passed"
    except (CheckFailure, OSError, subprocess.TimeoutExpired) as exc:
        evidence["failed_stage"] = stage
        evidence["failure"] = type(exc).__name__
    finally:
        evidence["cleanup"] = {"attempted": True, "completed": True}
        for kind, name in reversed(resources):
            if (kind, name) not in created:
                continue
            if not remove_owned(kind, name, run_id):
                evidence["cleanup"]["completed"] = False
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
            if Path(temporary).exists():
                evidence["cleanup"]["completed"] = False
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(output)
    return 0 if evidence["result"] == "passed" and evidence["cleanup"]["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
