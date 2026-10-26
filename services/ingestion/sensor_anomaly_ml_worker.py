"""One-shot, read-only tenant-isolated ML sensor-anomaly worker."""

from __future__ import annotations

import uuid
from typing import Any

from services.common.tenant_context import set_agent_source_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import require_feature

_WORKER_KEY = "sensor_anomaly_ml_source"
_RESOURCE = "sensor_anomaly_ml"
_ACTION = "analyze"


def run_sensor_anomaly_ml(
    location_id: str,
    *,
    sensor_id: str | None = None,
    train: bool = False,
) -> dict[str, Any]:
    """Run one location's model analysis through its signed reader identity.

    The worker deliberately has no shared-DSN fallback and never connects
    through ``services.ingestion.base.get_db``. Its database role can select
    only the location-filtered source view and cannot write alerts or readings.
    """
    require_feature("isolated_sensor_anomaly_ml_worker")
    try:
        canonical_location_id = str(uuid.UUID(str(location_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location-id must be a UUID") from exc
    if sensor_id is not None:
        try:
            sensor_id = str(uuid.UUID(str(sensor_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("sensor-id must be a UUID") from exc

    connection = get_worker_db(_WORKER_KEY)
    try:
        credential = get_worker_credential(_WORKER_KEY)
        set_agent_source_tenant_context(
            connection,
            credential=credential,
            location_id=canonical_location_id,
            resource=_RESOURCE,
            action=_ACTION,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_sensor_anomaly_ml_reader")

        from .ml_anomaly_detector import run_ml_check, save_models

        if train:
            return save_models(connection, canonical_location_id, signed_source=True)
        return run_ml_check(
            connection,
            location_id=canonical_location_id,
            sensor_id=sensor_id,
            signed_source=True,
        )
    finally:
        # Reads and the signed context share this transaction. Rollback clears
        # the transaction-local context and role before the connection closes.
        try:
            connection.rollback()
        finally:
            connection.close()
