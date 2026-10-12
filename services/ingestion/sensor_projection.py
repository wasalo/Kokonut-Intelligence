"""Shared sensor projection payload; the caller owns the source transaction."""

from .base import hash_payload, post_clickhouse_rows
from .clickhouse_outbox import enqueue


def project_sensor_reading(reading_id, location_id, plot_id, sensor_id, sensor_type,
                           value, unit, timestamp, quality="good", conn=None):
    """Enqueue atomically when given a connection; never commit or swallow errors."""
    columns = ["timestamp", "sensor_id", "sensor_type", "location_id", "plot_id",
               "value", "unit", "quality", "metadata"]
    rows = [[timestamp, str(sensor_id), str(sensor_type), str(location_id),
             str(plot_id) if plot_id else None, float(value), str(unit or ""), quality, {}]]
    if conn is not None:
        payload_hash = hash_payload({"reading_id": str(reading_id), "value": value,
                                     "timestamp": str(timestamp)})
        enqueue(conn, event_key=f"sensor_reading:sensor_readings:{reading_id}",
                source_table="sensor_reading", source_id=str(reading_id),
                target_table="sensor_readings", columns=columns, rows=rows,
                payload_hash=payload_hash)
        return
    # Explicit maintenance/demo use only; production callers pass their source
    # connection. The compatibility wrapper owns warning-only demo failures.
    post_clickhouse_rows("sensor_readings", columns, rows)
