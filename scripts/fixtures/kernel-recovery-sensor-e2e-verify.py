"""Read-only verification of the isolated single-reading recovery fixture."""

import json

from services.common.database import get_db
from services.ingestion.base import get_clickhouse

DATE = "2026-10-11"
SENSOR_ID = "f0000000-0000-4000-8000-000000000071"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


def main():
    conn = get_db()
    sink = get_clickhouse()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*),avg(value),min(value),max(value) "
                "FROM sensor_reading WHERE sensor_id=%s AND reading_date=%s",
                (SENSOR_ID, DATE),
            )
            source = cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM platform_event WHERE event_type='sensor_reading' "
                "AND payload->>'reading_date'=%s AND payload->>'sensor_id'=%s",
                (DATE, SENSOR_ID),
            )
            event_count = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*),count(DISTINCT source_id), "
                "count(*) FILTER (WHERE status='succeeded') "
                "FROM clickhouse_outbox WHERE source_table='sensor_reading' "
                "AND source_id IN (SELECT id::text FROM sensor_reading "
                "WHERE sensor_id=%s AND reading_date=%s)",
                (SENSOR_ID, DATE),
            )
            outbox = cur.fetchone()

        raw = sink.query(
            "SELECT count(),avg(value),min(value),max(value),"
            "uniqExact(sensor_id),uniqExact(location_id) FROM sensor_readings "
            "WHERE sensor_id='%s' AND toDate(timestamp)='%s'" % (SENSOR_ID, DATE)
        ).result_rows[0]
        view = sink.query(
            "SELECT total_readings,avg_value,min_value,max_value,active_sensors "
            "FROM v_daily_sensor_summary_v3 WHERE day='%s' AND location_id='%s' "
            "AND sensor_type='soil_moisture'" % (DATE, LOCATION_ID)
        ).result_rows

        assert source[0] == event_count == 2, (source, event_count)
        assert outbox == (2, 2, 2), outbox
        assert raw[0] == source[0], (raw, source)
        assert all(abs(float(a) - float(b)) < 1e-8 for a, b in zip(raw[1:4], source[1:])), (
            raw,
            source,
        )
        assert raw[4:] == (1, 1), raw
        assert view == [(2, float(source[1]), float(source[2]), float(source[3]), 1)], view

        print(
            json.dumps(
                {
                    "checks": {
                        "postgres_source_and_platform_events": True,
                        "outbox_distinct_sources_succeeded": True,
                        "raw_clickhouse_aggregate_parity": True,
                        "sensor_v3_daily_summary_parity": True,
                    },
                    "date": DATE,
                    "source_rows": source[0],
                    "event_rows": event_count,
                    "outbox_rows": outbox[0],
                    "outbox_succeeded": outbox[2],
                    "analytics_rows": raw[0],
                    "scope": "Read-only post-run verification. The earlier normal run_single call and delivery created these fixture rows; its immediate sink visibility check timed out at five seconds. A later read confirms sink and v3 parity; no latency guarantee is inferred.",
                }
            )
        )
    finally:
        sink.close()
        conn.close()


if __name__ == "__main__":
    main()
