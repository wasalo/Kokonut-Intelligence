"""Run one signed, location-scoped NOI snapshot reconciliation."""

from __future__ import annotations

import argparse
from uuid import UUID

from services.common.cli import print_json, run
from services.core.features import is_enabled


def reconcile(location_id: str) -> int:
    """Reconcile snapshots only through the bounded worker function."""
    from services.common.tenant_context import set_worker_tenant_context
    from services.common.worker_database import get_worker_credential, get_worker_db

    canonical_location_id = str(UUID(str(location_id)))
    credential = get_worker_credential("noi_snapshot")
    connection = get_worker_db("noi_snapshot")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=canonical_location_id,
            resource="noi_snapshot",
            action="reconcile",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.reconcile_noi_snapshot_for_location(%s::uuid)",
                (canonical_location_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("NOI snapshot worker returned no result")
            reconciled = int(row[0])
        connection.commit()
        return reconciled
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile crop-cycle NOI snapshots for one signed worker location"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args()
    try:
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")
    if not is_enabled("signed_noi_snapshot_worker"):
        parser.error("signed NOI snapshot worker is disabled")

    reconciled = reconcile(location_id)
    print_json({
        "status": "success",
        "reconciled": reconciled,
        "source": "v_crop_cycle_noi",
        "scope": "location",
        "location_id": location_id,
    })


if __name__ == "__main__":
    run(main)
