#!/usr/bin/env python3
"""Register authenticated synthetic media only in the dedicated recovery fixture."""

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import UUID

from kernel_recovery_guard import CONTAINER, query, require_fixture_database

LOCATION = "a0000000-0000-0000-0000-000000000001"
DEVICE = "kernel-recovery-adelphi-device"
MEDIA = {"uploaded": "f0000000-0000-4000-8000-000000000011",
         "attached": "f0000000-0000-4000-8000-000000000012"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root, schema_files = require_fixture_database()
    directory = args.directory
    if not directory.is_absolute() or directory.is_symlink():
        parser.error("Require an absolute private media directory")
    info = directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        parser.error("Media directory must be private and owned by this process")
    try:
        key = bytes.fromhex(os.environ.get("MOBILE_MEDIA_LOCAL_KEY", ""))
    except ValueError:
        parser.error("Invalid local media key configuration")
    if len(key) != 32:
        parser.error("Supply MOBILE_MEDIA_LOCAL_KEY through private secret custody")
    from Crypto.Cipher import AES

    records = json.loads(args.records.read_text())
    if not isinstance(records, list) or len(records) != 2:
        parser.error("Require exactly the uploaded and attached synthetic objects")
    validated, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            parser.error("Invalid media record")
        status = record.get("status")
        if status not in MEDIA or status in seen or record.get("media_id") != MEDIA[status]:
            parser.error("Unexpected or duplicate synthetic identity/status")
        scope = hashlib.sha256(DEVICE.encode()).hexdigest()[:20]
        object_key = f"private/field-collector/{LOCATION}/{scope}/{UUID(MEDIA[status]).hex}.jpg"
        if record.get("object_key") != object_key:
            parser.error("Object key must match the synthetic device/farm/media scope")
        filename = hashlib.sha256(object_key.encode()).hexdigest() + ".bin"
        descriptor = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                parser.error("Media objects must be owner-controlled private regular files")
            envelope = stream.read(2_000_033)
        if not 32 < len(envelope) <= 2_000_032 or envelope[:4] != b"KKM1":
            parser.error("Invalid encrypted object envelope")
        cipher = AES.new(key, AES.MODE_GCM, nonce=envelope[4:16])
        cipher.update(b"KKM1" + object_key.encode())
        try:
            body = cipher.decrypt_and_verify(envelope[32:], envelope[16:32])
        except ValueError:
            parser.error("Media authentication failed")
        if not body.startswith(b"\xff\xd8\xff"):
            parser.error("Fixture object must be JPEG data")
        size, digest = len(body), hashlib.sha256(body).hexdigest()
        if record.get("size_bytes") != size or record.get("content_sha256") != digest:
            parser.error("Fixture object size/hash differs from supplied metadata")
        validated.append({"media_id": MEDIA[status], "status": status, "object_key": object_key,
                          "size_bytes": size, "content_sha256": digest})
        seen.add(status)
    sql = (root / "scripts/fixtures/kernel-recovery-media.sql").read_text()
    if args.apply:
        query(sql, {"media_records": json.dumps(validated)})
    print(json.dumps({"applied": args.apply, "container": CONTAINER, "schema_files": schema_files,
                      "authenticated_objects": len(validated), "seed_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                      "scope": "Synthetic snapshot records only; no device token/enrollment authority, uploads or acceptance claims."}))


if __name__ == "__main__":
    main()
