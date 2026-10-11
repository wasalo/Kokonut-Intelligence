#!/usr/bin/env python3
"""Count Mosquitto v6 persistence chunks without printing identities or payloads.

Framing reference: eclipse-mosquitto/mosquitto v2.0.22 src/persist.h,
src/persist_read.c and src/persist_read_v5.c. This is not a full DB validator.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

CHUNKS = {1: "configuration", 2: "message_store", 3: "client_message",
          4: "retained_reference", 5: "subscription", 6: "client"}
MAGIC = b"\x00\xb5\x00mosquitto db"


def inventory(path):
    size = path.stat().st_size
    if size > 64 * 1024 * 1024:
        raise ValueError("Persistence file exceeds inventory limit")
    counts = dict.fromkeys(CHUNKS.values(), 0)
    with path.open("rb") as stream:
        header = stream.read(23)
        if len(header) != 23 or header[:15] != MAGIC:
            raise ValueError("Unrecognized persistence header")
        version = struct.unpack("!I", header[19:23])[0]
        if version != 6:
            raise ValueError("Only persistence version 6 is supported")
        while stream.tell() < size:
            framing = stream.read(8)
            if len(framing) != 8:
                raise ValueError("Truncated chunk header")
            kind, length = struct.unpack("!II", framing)
            if kind not in CHUNKS or length == 0 or stream.tell() + length > size:
                raise ValueError("Unsupported or truncated chunk")
            counts[CHUNKS[kind]] += 1
            stream.seek(length, 1)  # Skip private records, client IDs and payloads.
        if counts["configuration"] != 1:
            raise ValueError("Expected one configuration chunk")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"format_version": version, "bytes": size, "sha256": digest.hexdigest(),
            "chunk_counts": counts,
            "scope": "Persisted chunk framing only; no semantic payload/reference validation or in-memory backlog claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.path), indent=2))


if __name__ == "__main__":
    main()
