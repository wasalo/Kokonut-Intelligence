#!/usr/bin/env python3
"""Restore an encrypted media archive into a NEW private directory only."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.checkpoint / "manifest.json").read_text())
    if manifest.get("archive") != "media.tar.age":
        parser.error("Unsupported media checkpoint archive")
    archive_path = args.checkpoint / "media.tar.age"
    digest = hashlib.sha256()
    with archive_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != manifest.get("sha256") or archive_path.stat().st_size != manifest.get("bytes"):
        parser.error("Checkpoint ciphertext checksum mismatch")
    records = manifest.get("files")
    if not isinstance(records, list):
        parser.error("Missing object inventory")
    expected = {}
    for record in records:
        if (not re.fullmatch(r"[0-9a-f]{64}\.bin", record.get("file", ""))
                or record["file"] in expected
                or not isinstance(record.get("bytes"), int)
                or not 32 < record["bytes"] <= 2_000_032
                or not re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", ""))):
            parser.error("Invalid object inventory")
        expected[record["file"]] = record
    destination = args.destination
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        parser.error("Require an absolute unused restore destination")
    staging = destination.with_name(destination.name + ".partial")
    staging.mkdir(mode=0o700)
    process = subprocess.Popen(["age", "-d", "-i", str(args.identity), str(archive_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    seen = set()
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if (member.name not in expected or member.name in seen or not member.isfile()
                        or member.size != expected[member.name]["bytes"]):
                    raise ValueError("Unexpected, duplicate or unsafe archive member")
                body = archive.extractfile(member)
                digest = hashlib.sha256()
                # No extract/extractall: validated flat names only, exclusive create.
                with (staging / member.name).open("xb") as output:
                    for chunk in iter(lambda: body.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != expected[member.name]["sha256"]:
                    raise ValueError("Restored ciphertext object checksum mismatch")
                seen.add(member.name)
        # Drain to EOF so age can finish authenticating the entire ciphertext.
        while process.stdout.read(1024 * 1024):
            pass
        process.stdout.close()
        if process.wait() != 0 or seen != set(expected):
            raise ValueError("Decryption failed or object inventory incomplete")
    finally:
        if process.poll() is None:
            process.stdout.close()
            process.terminate()
            process.wait()
    descriptor = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    # Exclusive mkdir/link avoid replacing an existing destination or object.
    # Operators must keep the new directory disconnected from the application.
    destination.mkdir(mode=0o700)
    for name in sorted(seen):
        os.link(staging / name, destination / name)
        (staging / name).unlink()
    staging.rmdir()
    print(f"Restored {len(seen)} encrypted media objects; DB/AES authentication still required")


if __name__ == "__main__":
    main()
