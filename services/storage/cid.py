"""Development-only content-addressed storage adapter.

The production MRV flow should pin payloads to IPFS/Filecoin or another
content-addressed provider. This adapter gives local development the same
interface without sending private evidence outside the developer machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = Path(".local-cid-store")
LOCAL_CID_PREFIX = "local://sha256/"


def canonical_bytes(payload: Any) -> bytes:
    """Serialize payload deterministically for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def hash_payload(payload: Any) -> str:
    """Return SHA-256 hex digest for a payload."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def make_local_cid(payload: Any) -> str:
    """Return a local development CID for a payload."""
    return f"{LOCAL_CID_PREFIX}{hash_payload(payload)}"


def _path_for_hash(digest: str, store_dir: Path) -> Path:
    return store_dir / "sha256" / f"{digest}.json"


def pin_json(payload: Any, store_dir: Path | str = DEFAULT_STORE_DIR) -> dict[str, str]:
    """Persist JSON payload locally and return CID metadata."""
    store_path = Path(store_dir)
    digest = hash_payload(payload)
    output_path = _path_for_hash(digest, store_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_bytes(payload))
    return {
        "cid": f"{LOCAL_CID_PREFIX}{digest}",
        "hash": digest,
        "path": str(output_path),
        "adapter": "local-sha256",
    }


def read_json(cid: str, store_dir: Path | str = DEFAULT_STORE_DIR) -> Any:
    """Read a locally pinned JSON payload by CID."""
    if not cid.startswith(LOCAL_CID_PREFIX):
        raise ValueError(f"Unsupported local CID: {cid}")
    digest = cid.removeprefix(LOCAL_CID_PREFIX)
    input_path = _path_for_hash(digest, Path(store_dir))
    return json.loads(input_path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Local CID adapter for development")
    parser.add_argument("--pin-json", help="JSON string to pin locally")
    parser.add_argument("--read", help="Read a local CID")
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR), help="Local store directory")
    args = parser.parse_args()

    if args.pin_json:
        metadata = pin_json(json.loads(args.pin_json), args.store_dir)
        print(json.dumps(metadata, indent=2, sort_keys=True))
        return

    if args.read:
        print(json.dumps(read_json(args.read, args.store_dir), indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
