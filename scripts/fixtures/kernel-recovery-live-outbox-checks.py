"""Live driver recovery checks against dedicated fixture PostgreSQL/ClickHouse."""
import json
from unittest.mock import patch

from services.common.database import get_db
from services.ingestion import clickhouse_outbox as outbox
from services.ingestion.base import get_clickhouse


def main():
    conn = get_db()
    sink = get_clickhouse()
    checks = {}
    held = []

    def q(sql, args=()):
        with conn.cursor() as cur:
            cur.execute(sql, args or None)
            result = cur.fetchall() if cur.description else []
        conn.commit()
        return result

    try:
        assert q('SELECT current_database()') == [('kokonut_intelligence',)]
        assert sink.query('SELECT currentDatabase()').result_rows == [('kokonut_analytics',)]
        assert sink.query("SELECT count() FROM sensor_readings WHERE sensor_type='soil_moisture_live3'").result_rows == [(0,)]
        assert q("SELECT count(*) FROM clickhouse_outbox WHERE event_key LIKE 'kernel-recovery-live3:%'") == [(0,)]
        # Retained prior synthetic checks include pending replay state. Hold it
        # temporarily so this worker only claims the live transport fixture.
        with conn.cursor() as cur:
            cur.execute("SELECT id,available_at,event_key FROM clickhouse_outbox WHERE status IN ('pending','retryable') FOR UPDATE")
            held = cur.fetchall()
            assert all(row[2].startswith('kernel-recovery') for row in held)
            for row in held:
                cur.execute("UPDATE clickhouse_outbox SET available_at=NOW()+INTERVAL '1 day' WHERE id=%s", (row[0],))
        conn.commit()
        columns = ['timestamp', 'sensor_id', 'sensor_type', 'location_id', 'plot_id', 'value', 'unit', 'quality', 'metadata']
        for index, value in enumerate([10, 20, 30]):
            payload = [['2026-10-10T12:00:00+00:00', 'kernel-recovery-live-sensor', 'soil_moisture_live3',
                        'a0000000-0000-0000-0000-000000000001', None, value, 'percent', 'good', {}]]
            outbox.enqueue(conn, event_key=f'kernel-recovery-live3:{index}', source_table='synthetic_recovery',
                           source_id=f'live-{index}', target_table='sensor_readings', columns=columns,
                           rows=payload, payload_hash=str(index) * 64)
        conn.commit()
        with patch.object(outbox, '_finish', side_effect=RuntimeError('Synthetic crash after sink insert before ack')):
            try:
                outbox.deliver_batch(conn, 'live-former-worker', 1)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Crash injection did not execute')
        assert sink.query("SELECT count() FROM sensor_readings WHERE sensor_type='soil_moisture_live3'").result_rows == [(1,)]
        q("UPDATE clickhouse_outbox SET lease_expires_at=NOW()-INTERVAL '1 second' WHERE event_key LIKE 'kernel-recovery-live3:%' AND status='processing'")
        assert outbox.deliver_batch(conn, 'live-recovery-worker', 3) == {'claimed': 3, 'delivered': 3, 'failed': 0}
        assert sink.query("SELECT count() FROM sensor_readings WHERE sensor_type='soil_moisture_live3'").result_rows == [(3,)]
        checks['insert_before_ack_crash_replay_deduplicated_within_window'] = True
        assert outbox.deliver_batch(conn, 'live-recovery-worker', 3) == {'claimed': 0, 'delivered': 0, 'failed': 0}
        checks['successful_records_not_redelivered'] = True
        pg = q("SELECT count(*),avg((rows->0->5)::text::numeric),min((rows->0->5)::text::numeric),max((rows->0->5)::text::numeric) FROM clickhouse_outbox WHERE event_key LIKE 'kernel-recovery-live3:%'")[0]
        daily = sink.query("SELECT total_readings,avg_value,min_value,max_value,active_sensors,suspect_readings FROM v_daily_sensor_summary_v3 WHERE sensor_type='soil_moisture_live3'").result_rows
        assert daily == [(pg[0], float(pg[1]), float(pg[2]), float(pg[3]), 1, 0)], (pg, daily)
        assert sink.query("SELECT count() FROM sensor_readings WHERE plot_id IS NULL AND sensor_type='soil_moisture_live3'").result_rows == [(3,)]
        assert sink.query("SELECT count() FROM system.tables WHERE database='default' AND name='sensor_readings'").result_rows == [(0,)]
        checks['json_datetime_nullable_uuid_and_selected_database_delivery'] = True
        checks['v3_summary_matches_postgres_outbox_payload_aggregates'] = True
        assert q("SELECT count(*) FROM clickhouse_outbox WHERE event_key LIKE 'kernel-recovery-live3:%' AND status='succeeded'") == [(3,)]
        print(json.dumps({'checks': checks, 'raw_readings': 3, 'daily_average': daily[0][1], 'scope': 'Live clickhouse-connect and PostgreSQL outbox; one deterministic insert-before-ack crash inside configured block window. Canonical domain source ingestion, window eviction, restart, concurrent writers and other payload types remain unassessed.'}))
    finally:
        conn.rollback()
        for row in held:
            q('UPDATE clickhouse_outbox SET available_at=%s WHERE id=%s', (row[1], row[0]))
        sink.close()
        conn.close()


if __name__ == '__main__':
    main()
