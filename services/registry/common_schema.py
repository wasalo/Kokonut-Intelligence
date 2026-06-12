"""Kokonut Common Data Schema validation and MRV request helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.storage.cid import hash_payload, make_local_cid, pin_json

REQUIRED_FARM_FIELDS = [
    "project_date",
    "forecasted_budget",
    "land_size",
    "project_location",
    "source_of_funding",
    "revenue_streams",
    "governance_mechanism",
    "token_allocation",
    "public_goods_allocation",
    "project_summary",
    "local_problem",
    "proposed_solution",
    "target_market",
]

VALID_GOVERNANCE = {"moloch_dao", "guilds", "multisig", "cooperative"}
VALID_MRV_TYPES = {"ground", "remote", "community", "mixed"}


def example_farm_record() -> dict[str, Any]:
    """Return a minimal Common Data Schema example."""
    return {
        "project_date": "2025-09-01",
        "forecasted_budget": 85000,
        "land_size": 120000,
        "project_location": {
            "coordinates": "-0.100000,34.750000",
            "region": "Kisumu County",
            "country": "Kenya",
        },
        "source_of_funding": "Kokonut DAO pilot allocation",
        "revenue_streams": ["maize", "cassava", "beans", "bioinputs"],
        "governance_mechanism": "cooperative",
        "token_allocation": "70% operators, 20% contributors, 10% public goods reserve",
        "public_goods_allocation": 10,
        "project_summary": "Mixed-crop regenerative pilot with MRV-ready reporting.",
        "local_problem": "Unstable farm income and degraded soil health.",
        "proposed_solution": "Governed crop economics, bioinputs, MRV, and partner sales.",
        "target_market": ["local_processors", "direct_buyers"],
    }


def validate_farm_record(payload: dict[str, Any]) -> list[str]:
    """Validate the 13 Kokonut Common Data Schema fields."""
    errors: list[str] = []
    for field in REQUIRED_FARM_FIELDS:
        if field not in payload or payload[field] in (None, "", []):
            errors.append(f"Missing required field: {field}")

    location = payload.get("project_location") or {}
    if not isinstance(location, dict):
        errors.append("project_location must be an object")
    else:
        for field in ("coordinates", "region", "country"):
            if not location.get(field):
                errors.append(f"Missing project_location.{field}")

    governance = payload.get("governance_mechanism")
    if governance and governance not in VALID_GOVERNANCE:
        errors.append(f"Invalid governance_mechanism: {governance}")

    allocation = payload.get("public_goods_allocation")
    if allocation is not None:
        try:
            value = float(allocation)
            if value < 0 or value > 100:
                errors.append("public_goods_allocation must be between 0 and 100")
        except (TypeError, ValueError):
            errors.append("public_goods_allocation must be numeric")

    for field in ("revenue_streams", "target_market"):
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"{field} must be a list")

    return errors


def prepare_registry_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Prepare validated Common Data Schema metadata for database/API writes."""
    errors = validate_farm_record(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "payload": payload,
        "record_hash": hash_payload(payload),
        "schema_version": "common-data-schema-v1",
    }


def prepare_mrv_payload(payload: dict[str, Any], pin_local: bool = False) -> dict[str, Any]:
    """Prepare a Kokonut MRV payload without exposing private evidence."""
    measurement_type = payload.get("measurement_type")
    if measurement_type not in VALID_MRV_TYPES:
        raise ValueError(f"measurement_type must be one of {sorted(VALID_MRV_TYPES)}")

    public_payload = {
        "farm_id": payload.get("farm_id"),
        "timestamp": payload.get("timestamp"),
        "measurement_type": measurement_type,
        "ground": payload.get("ground"),
        "remote": payload.get("remote"),
        "community": payload.get("community"),
    }
    public_payload = {k: v for k, v in public_payload.items() if v is not None}

    if pin_local:
        cid_metadata = pin_json(public_payload)
    else:
        cid_metadata = {
            "cid": make_local_cid(public_payload),
            "hash": hash_payload(public_payload),
            "adapter": "local-sha256",
        }

    return {
        "public_payload": public_payload,
        "payload_cid": cid_metadata["cid"],
        "payload_hash": cid_metadata["hash"],
        "storage_adapter": cid_metadata["adapter"],
    }


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut Farm Registry helper")
    parser.add_argument("--example-farm-record", action="store_true", help="Print a Common Data Schema example")
    parser.add_argument("--validate-farm-record", help="Validate a Common Data Schema JSON file")
    parser.add_argument("--prepare-mrv", help="Prepare an MRV JSON payload")
    parser.add_argument("--pin-local", action="store_true", help="Persist prepared payload to local CID store")
    args = parser.parse_args()

    if args.example_farm_record:
        print(json.dumps(example_farm_record(), indent=2, sort_keys=True))
        return

    if args.validate_farm_record:
        prepared = prepare_registry_record(_load_json(args.validate_farm_record))
        print(json.dumps(prepared, indent=2, sort_keys=True))
        return

    if args.prepare_mrv:
        prepared = prepare_mrv_payload(_load_json(args.prepare_mrv), pin_local=args.pin_local)
        print(json.dumps(prepared, indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
