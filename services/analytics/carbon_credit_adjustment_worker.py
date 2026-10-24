"""Run a signed, location-scoped, read-only carbon credit adjustment check."""

from __future__ import annotations

import argparse
from uuid import UUID

from services.common.cli import print_json, run
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled

_WORKER_KEY = "credit_adjustment"
_RESOURCE = "carbon_credit_adjustment"
_ACTION = "read"


def check(location_id: str) -> list[dict]:
    """Read adjustment candidates only through the signed bounded function."""
    canonical_location_id = str(UUID(str(location_id)))
    credential = get_worker_credential(_WORKER_KEY)
    connection = get_worker_db(_WORKER_KEY)
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=canonical_location_id,
            resource=_RESOURCE,
            action=_ACTION,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT credit_code, current_sequestration_tonnes,
                       recomputed_sequestration_tonnes
                  FROM kokonut_security.credit_adjustment_snapshot_for_location(%s::uuid)
                """,
                (canonical_location_id,),
            )
            rows = cursor.fetchall()

        results = []
        for credit_code, current_tonnes, recomputed_tonnes in rows:
            old_value = float(current_tonnes or 0)
            # Keep the rounding contract of compute_carbon_balance(), which
            # reports sequestration to four decimal places before the legacy
            # adjustment threshold is applied.
            new_value = round(float(recomputed_tonnes or 0), 4)
            delta_pct = abs((new_value - old_value) / old_value * 100) if old_value > 0 else 0
            if delta_pct > 0.1:
                results.append({
                    "credit_code": credit_code,
                    "current_tonnes": old_value,
                    "recomputed_tonnes": new_value,
                    "delta_pct": round(delta_pct, 4),
                    "needs_adjustment": True,
                })
        connection.commit()
        return results
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Read-only carbon credit adjustment check for one signed location"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    args = parser.parse_args(argv)
    try:
        location_id = str(UUID(str(args.location_id)))
    except (TypeError, ValueError, AttributeError):
        parser.error("--location-id must be a UUID")
    if not is_enabled("signed_credit_adjustment_worker"):
        parser.error("signed credit adjustment worker is disabled")

    results = check(location_id)
    print_json({
        "status": "success",
        "scope": "location",
        "location_id": location_id,
        "count": len(results),
        "adjustments": results,
    })


if __name__ == "__main__":
    run(main)
