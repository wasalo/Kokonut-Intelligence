#!/usr/bin/env python3
"""Archive quiesced encrypted local media, bound to a scoped DB checkpoint."""

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
from pathlib import Path


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--database-checkpoint", type=Path, required=True)
    parser.add_argument("--key-reference", required=True,
                        help="Secret custody reference, never the encryption key")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--quiesced", action="store_true",
                        help="Operator confirms uploads, expiry/deletion and writes are stopped")
    args = parser.parse_args()
    if not args.quiesced:
        parser.error("Quiesce writes, uploads and expiry/deletion before capture")
    root = args.directory
    if not root.is_absolute() or root.is_symlink():
        parser.error("Use an absolute private media directory, not a symlink")
    metadata = root.stat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        parser.error("Run as the media owner; directory must have mode 0700")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:/-]{0,199}", args.key_reference):
        parser.error("Use a short secret custody label, not key contents")
    if re.fullmatch(r"[0-9a-fA-F]{64}", args.key_reference):
        parser.error("Do not provide an encryption key as its reference")
    database = json.loads(args.database_checkpoint.read_text())
    archive_name = database.get("archive", "")
    if Path(archive_name).name != archive_name or archive_name != "postgres.dump.age":
        parser.error("Require a scoped kernel-checkpoint.sh manifest")
    database_archive = args.database_checkpoint.parent / archive_name
    if fingerprint(database_archive) != database.get("sha256"):
        parser.error("Database checkpoint ciphertext checksum mismatch")
    paths = sorted(root.iterdir())
    if any(not re.fullmatch(r"[0-9a-f]{64}\.bin", p.name) for p in paths):
        parser.error("Unexpected files or unfinished uploads; review before capture")
    args.destination.mkdir(mode=0o700)
    partial = args.destination / "media.tar.age.partial"
    process = subprocess.Popen(["age", "-r", args.recipient, "-o", str(partial)],
                               stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    records = []
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            for path in paths:
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(before.st_mode) or before.st_mode & 0o077
                            or before.st_uid != os.getuid()):
                        raise ValueError("Media files must be private regular files")
                    if not 32 < before.st_size <= 2_000_032 or stream.read(4) != b"KKM1":
                        raise ValueError("Unexpected encrypted media envelope")
                    stream.seek(0)
                    item = tarfile.TarInfo(path.name)
                    item.size, item.mode = before.st_size, 0o600
                    archive.addfile(item, stream)
                    stream.seek(0)
                    digest = hashlib.sha256(stream.read()).hexdigest()
                    after = os.fstat(stream.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_size, after.st_mtime_ns, after.st_ctime_ns
                    ) or path.stat(follow_symlinks=False).st_ino != before.st_ino:
                        raise ValueError("Media changed during capture")
                    records.append({"file": path.name, "bytes": before.st_size, "sha256": digest})
        process.stdin.close()
        if process.wait() != 0 or sorted(root.iterdir()) != paths:
            raise ValueError("Archive incomplete or directory changed during capture")
    finally:
        if process.poll() is None:
            process.stdin.close()
            process.terminate()
            process.wait()
    output = args.destination / "media.tar.age"
    partial.rename(output)
    manifest = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "archive": output.name, "sha256": fingerprint(output), "bytes": output.stat().st_size,
        "database_archive_sha256": database["sha256"],
        "key_reference": args.key_reference, "files": records,
        "scope": "Encrypted local media files; key excluded. Operator-confirmed quiescence, not a distributed snapshot. Envelope authentication and DB-reference parity not exercised.",
        "restore_rehearsed": False,
    }
    (args.destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Encrypted media checkpoint captured: {len(records)} objects; restore pending")


if __name__ == "__main__":
    main()
