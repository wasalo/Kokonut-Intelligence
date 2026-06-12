"""Capability manifest helpers for Kokonut Agentic Marketplace metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.storage.cid import hash_payload, make_local_cid, pin_json

REQUIRED_MANIFEST_FIELDS = ["agent_name", "version", "description", "inputs", "outputs"]


def example_manifest(agent_name: str = "kokonut-mrv-reporter") -> dict[str, Any]:
    """Return a Kokonut-compatible capability manifest example."""
    return {
        "agent_name": agent_name,
        "version": "1.0.0",
        "description": "Prepares MRV events and EAS attestation request metadata for Kokonut farms.",
        "inputs": {
            "farm_id": {"type": "string", "required": True},
            "period_start": {"type": "string", "format": "ISO8601", "required": True},
            "period_end": {"type": "string", "format": "ISO8601", "required": True},
        },
        "outputs": {
            "mrv_event_id": {"type": "string", "format": "uuid"},
            "eas_attestation_uid": {"type": "string"},
            "ipfs_cid": {"type": "string"},
        },
        "pricing": {"token": "USDC", "chain": "base", "per_task_usd": 5.0},
        "marketplace_logic": "Kokonut-Agentic-Marketplace",
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate required metadata for an agent capability manifest."""
    errors: list[str] = []
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest or manifest[field] in (None, "", {}, []):
            errors.append(f"Missing required field: {field}")
    for field in ("inputs", "outputs"):
        if field in manifest and not isinstance(manifest[field], dict):
            errors.append(f"{field} must be an object")
    return errors


def prepare_manifest(manifest: dict[str, Any], pin_local: bool = False) -> dict[str, Any]:
    """Validate and prepare manifest CID metadata."""
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))

    cid_metadata = pin_json(manifest) if pin_local else {
        "cid": make_local_cid(manifest),
        "hash": hash_payload(manifest),
        "adapter": "local-sha256",
    }
    return {
        "manifest": manifest,
        "manifest_cid": cid_metadata["cid"],
        "manifest_hash": cid_metadata["hash"],
        "storage_adapter": cid_metadata["adapter"],
        "marketplace_logic": manifest.get("marketplace_logic", "Kokonut-Agentic-Marketplace"),
    }


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut agent capability manifest helper")
    parser.add_argument("--example", nargs="?", const="kokonut-mrv-reporter", help="Print example manifest")
    parser.add_argument("--validate", help="Validate a manifest JSON file")
    parser.add_argument("--pin-local", action="store_true", help="Persist manifest to local CID store")
    args = parser.parse_args()

    if args.example:
        print(json.dumps(example_manifest(args.example), indent=2, sort_keys=True))
        return

    if args.validate:
        print(json.dumps(prepare_manifest(_load_json(args.validate), pin_local=args.pin_local), indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
