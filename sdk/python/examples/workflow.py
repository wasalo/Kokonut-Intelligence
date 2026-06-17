"""Example: Full harvest lifecycle (create -> submit -> verify -> publish).

Usage:
    KOKONUT_TOKEN=... python examples/workflow.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kokonut import KokonutClient

BASE_URL = os.environ.get("KOKONUT_BASE_URL", "http://localhost:8055")
TOKEN = os.environ.get("KOKONUT_TOKEN")

VALID_TRANSITIONS = {
    "draft": "submitted",
    "submitted": "verified",
    "verified": "published",
    "rejected": "submitted",
}


def transition_harvest(client: KokonutClient, harvest_id: str, target_status: str) -> dict:
    current = client.harvest_events.get(harvest_id)
    print(f"  Current state: {current.get('status')}")

    if current.get("status") == target_status:
        print(f"  Already in target state: {target_status}")
        return current

    expected = VALID_TRANSITIONS.get(current.get("status", ""))
    if expected != target_status:
        raise ValueError(
            f"Invalid transition: {current.get('status')} -> {target_status} "
            f"(expected -> {expected})"
        )

    updated = client.harvest_events.update(harvest_id, {"status": target_status})
    print(f"  Transitioned to: {updated.get('status')}")
    return updated


def main() -> None:
    client = KokonutClient(BASE_URL, token=TOKEN)

    if not TOKEN:
        client.login("admin@example.com", os.environ.get("ADMIN_PASSWORD", "changeme"))

    # These would be real UUIDs from your platform
    crop_cycle_id = "PLACEHOLDER_CROP_CYCLE_ID"
    plot_id = "PLACEHOLDER_PLOT_ID"
    location_id = "PLACEHOLDER_LOCATION_ID"

    # Step 1: Create draft harvest event
    print("1. Creating draft harvest event...")
    now = datetime.now(timezone.utc).isoformat()
    harvest = client.harvest_events.create({
        "crop_cycle_id": crop_cycle_id,
        "plot_id": plot_id,
        "location_id": location_id,
        "harvest_date": now,
        "quantity": 1500,
        "unit": "kg",
        "quality_grade": "A",
        "loss_amount": 80,
        "loss_unit": "kg",
        "loss_reason": "moisture_loss_during_drying",
        "status": "draft",
        "notes": "Field harvest from Plot A",
    })
    print(f"  Harvest created: {harvest['id']}\n")

    # Step 2: Submit after field data entry is complete
    print("2. Submitting harvest data...")
    transition_harvest(client, harvest["id"], "submitted")
    client.harvest_events.update(harvest["id"], {
        "quantity": 1420,
        "loss_amount": 80,
    })
    print("  Updated quantity to net weight\n")

    # Step 3: Submit for verification
    print("3. Submitting for verification...")
    transition_harvest(client, harvest["id"], "verified")
    client.harvest_events.update(harvest["id"], {
        "verified_by": "field-supervisor-001",
    })
    print("  Recorded verifier\n")

    # Step 4: Publish
    print("4. Publishing verified harvest...")
    transition_harvest(client, harvest["id"], "published")
    print("  Harvest is now publicly visible\n")

    # Step 5: Record corresponding sale
    print("5. Recording corresponding sale...")
    sale = client.sales_events.create({
        "crop_cycle_id": crop_cycle_id,
        "harvest_id": harvest["id"],
        "location_id": location_id,
        "buyer": "Local Cooperative",
        "buyer_type": "cooperative",
        "sale_date": now,
        "quantity": 1420,
        "unit": "kg",
        "price_per_unit": 8.50,
        "total_amount": 12070,
        "currency": "USD",
        "payment_status": "pending",
        "status": "draft",
    })
    print(f"  Sale created: {sale['id']}\n")

    # Step 6: Create attestation record
    print("6. Creating attestation record...")
    attestation = client.attestations.create({
        "schema_id": "PLACEHOLDER_SCHEMA_ID",
        "subject_type": "harvest_event",
        "subject_id": harvest["id"],
        "claim_type": "verified_harvest",
        "claim_data": {
            "crop_cycle_id": crop_cycle_id,
            "quantity": 1420,
            "unit": "kg",
            "quality_grade": "A",
            "loss_rate_pct": 5.33,
            "verified_by": "field-supervisor-001",
        },
        "status": "draft",
    })
    print(f"  Attestation created: {attestation['id']}")

    print("\nWorkflow complete!")
    print(f"  Harvest:  {harvest['id']}")
    print(f"  Sale:     {sale['id']}")
    print(f"  Attestation: {attestation['id']}")


if __name__ == "__main__":
    main()
