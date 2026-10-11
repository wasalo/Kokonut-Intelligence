"""Inspect, checkpoint, and restore a gateway audit journal without exposing rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path

from services.common.cli import print_json, run
from services.gateway.audit_spool import MAX_EVENT_BYTES, GatewayAuditSpool


def _private_directory(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("use an absolute, non-symlink private directory")
    metadata = path.stat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o077
    ):
        raise ValueError("directory must be owned by this process with no group/world access")


def _private_file(path: Path) -> os.stat_result:
    _private_directory(path.parent)
    if path.is_symlink():
        raise ValueError("journal path cannot be a symlink")
    metadata = path.stat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o077
    ):
        raise ValueError("journal must be a private regular file owned by this process")
    return metadata


def _read_only_uri(path: Path) -> str:
    return f"{path.as_uri()}?mode=ro"


def _validate(path: Path) -> dict[str, int | str]:
    _private_file(path)
    connection = sqlite3.connect(_read_only_uri(path), uri=True, timeout=5)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        objects = connection.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        if objects != [("table", "pending_gateway_audit")]:
            raise ValueError("file is not a gateway audit journal")
        columns = connection.execute("PRAGMA table_info(pending_gateway_audit)").fetchall()
        if [row[1] for row in columns] != ["sequence", "event_id", "payload_json", "queued_at"]:
            raise ValueError("gateway audit journal schema is invalid")
        rows = connection.execute(
            "SELECT event_id, payload_json FROM pending_gateway_audit ORDER BY sequence"
        ).fetchall()
        for event_id, payload_json in rows:
            if not isinstance(event_id, str) or not isinstance(payload_json, str):
                raise ValueError("journal row has invalid field types")
            event = json.loads(payload_json)
            if not isinstance(event, dict) or event.get("event_id") != event_id:
                raise ValueError("journal event identity does not match its payload")
            if len(payload_json.encode("utf-8")) > MAX_EVENT_BYTES:
                raise ValueError("journal event exceeds the supported serialized size")
        return {
            "integrity": integrity[0],
            "pending_events": len(rows),
            "bytes": path.stat().st_size,
        }
    finally:
        connection.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_journal(source: Path, destination: Path) -> dict[str, int | str]:
    _private_file(source)
    _private_directory(destination.parent)
    if destination.exists() or destination.is_symlink() or source.resolve() == destination.resolve():
        raise ValueError("destination must be a new file distinct from the source")

    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    os.close(descriptor)
    source_connection = None
    destination_connection = None
    try:
        source_connection = sqlite3.connect(_read_only_uri(source), uri=True, timeout=5)
        destination_connection = sqlite3.connect(str(destination), timeout=5)
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA journal_mode=DELETE")
        destination_connection.commit()
    except Exception:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        destination_connection.close()
        source_connection.close()

    os.chmod(destination, 0o600)
    descriptor = os.open(destination, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)

    copied = _validate(destination)
    return {**copied, "sha256": _sha256(destination)}


def _default_spool_path() -> Path:
    return GatewayAuditSpool().path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="show journal state without event contents")
    status.add_argument("--path", type=Path, default=_default_spool_path())

    verify = commands.add_parser("verify", help="check a journal/checkpoint without printing records")
    verify.add_argument("--path", type=Path, required=True)

    checkpoint = commands.add_parser("checkpoint", help="make a consistent new SQLite snapshot")
    checkpoint.add_argument("--path", type=Path, default=_default_spool_path())
    checkpoint.add_argument("--destination", type=Path, required=True)

    restore = commands.add_parser("restore", help="copy a verified checkpoint to a new file")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            path = args.path.expanduser()
            if path.is_symlink():
                raise ValueError("journal path cannot be a symlink")
            capacity = GatewayAuditSpool(path=str(path)).capacity_status()
            if not path.exists():
                result = {"path": str(path), "exists": False, **capacity}
            else:
                result = {
                    "path": str(path),
                    "exists": True,
                    **_validate(path),
                    **capacity,
                }
        elif args.command == "verify":
            path = args.path.expanduser()
            result = {"path": str(path), **_validate(path)}
        elif args.command == "checkpoint":
            source = args.path.expanduser()
            destination = args.destination.expanduser()
            result = {
                "checkpoint": str(destination),
                **_copy_journal(source, destination),
            }
        else:
            source = args.source.expanduser()
            destination = args.destination.expanduser()
            result = {
                "restored_copy": str(destination),
                **_copy_journal(source, destination),
            }
        print_json(result)
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"gateway audit journal operation failed ({type(exc).__name__})") from exc


if __name__ == "__main__":
    run(main)
