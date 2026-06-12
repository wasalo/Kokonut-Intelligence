"""Prepare privacy-preserving EAS attestation request payloads.

This module does not sign or submit transactions. It prepares public metadata,
local-development CIDs, and private payload hashes so sensitive evidence can
remain off-chain until a configured attestation service handles signing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.storage.cid import hash_payload, make_local_cid, pin_json


def prepare_attestation_request(
    subject_type: str,
    subject_id: str,
    event_type: str,
    public_payload: dict[str, Any],
    private_payload: dict[str, Any] | None = None,
    chain: str | None = None,
    pin_local: bool = False,
) -> dict[str, Any]:
    """Prepare attestation request metadata without leaking private payloads."""
    cid_metadata = pin_json(public_payload) if pin_local else {
        "cid": make_local_cid(public_payload),
        "hash": hash_payload(public_payload),
        "adapter": "local-sha256",
    }

    request = {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "event_type": event_type,
        "chain": chain,
        "payload_cid": cid_metadata["cid"],
        "payload_hash": cid_metadata["hash"],
        "storage_adapter": cid_metadata["adapter"],
        "public_payload": public_payload,
        "private_payload_hash": hash_payload(private_payload) if private_payload is not None else None,
        "sensitive_data_policy": "Private evidence is kept off-chain; only CID/hash metadata is prepared for EAS.",
    }
    return {k: v for k, v in request.items() if v is not None}


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare EAS attestation request metadata")
    parser.add_argument("--subject-type", help="Subject table/type")
    parser.add_argument("--subject-id", help="Subject UUID or identifier")
    parser.add_argument("--event-type", help="Attestation event type")
    parser.add_argument("--payload-file", help="Public payload JSON file")
    parser.add_argument("--private-payload-file", help="Private payload JSON file to hash only")
    parser.add_argument("--chain", help="Target chain label")
    parser.add_argument("--pin-local", action="store_true", help="Persist public payload to local CID store")
    args = parser.parse_args()

    if args.payload_file:
        if not args.subject_type or not args.subject_id or not args.event_type:
            parser.error("--subject-type, --subject-id, and --event-type are required with --payload-file")
        private_payload = _load_json(args.private_payload_file) if args.private_payload_file else None
        request = prepare_attestation_request(
            args.subject_type,
            args.subject_id,
            args.event_type,
            _load_json(args.payload_file),
            private_payload=private_payload,
            chain=args.chain,
            pin_local=args.pin_local,
        )
        print(json.dumps(request, indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
