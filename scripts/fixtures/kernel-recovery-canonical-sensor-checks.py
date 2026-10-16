"""Canonical sensor helper transactions and live analytics parity, isolated only."""
import json
from unittest.mock import patch

from services.common.database import get_db
from services.ingestion import clickhouse_outbox as outbox
from services.ingestion.base import get_clickhouse
from services.ingestion.sensor_ingester import get_sensor_by_id_or_slug, insert_reading, insert_reading_clickhouse

SENSOR = 'f0000000-0000-4000-8000-000000000071'
SLUG = 'kernel-recovery-canonical-sensor'
LOCATION = 'a0000000-0000-0000-0000-000000000001'
DAY = '2026-10-09'


def main():
    conn = get_db()
    sink = get_clickhouse()
    held = []
    checks = {}

    def q(sql, args=()):
        with conn.cursor() as cur:
            cur.execute(sql, args or None)
            result = cur.fetchall() if cur.description else []
        conn.commit()
        return result

    try:
        assert q('SELECT current_database()') == [('kokonut_intelligence',)]
        assert q('SELECT count(*) FROM sensor_device WHERE id=%s', (SENSOR,)) == [(0,)]
        assert sink.query("SELECT count() FROM sensor_readings WHERE sensor_id='%s'" % SENSOR).result_rows == [(0,)]
        q("""INSERT INTO sensor_device(id,name,slug,sensor_type_id,location_id,protocol,metadata)
            SELECT %s,'Synthetic canonical recovery sensor',%s,id,
            %s,'manual','{"synthetic_recovery_fixture":true}'
            FROM sensor_type WHERE name='soil_moisture'""", (SENSOR, SLUG, LOCATION))
        info = get_sensor_by_id_or_slug(conn, SLUG, LOCATION)
        assert info is not None
        # Roll back a real source insertion when outbox enqueue is unavailable.
        insert_reading(conn, info, DAY, '11:00:00', 5)
        with patch('services.ingestion.sensor_projection.enqueue', side_effect=RuntimeError('Synthetic enqueue failure')):
            try:
                insert_reading_clickhouse(info, DAY, '11:00:00', 5, conn=conn)
            except RuntimeError:
                conn.rollback()
            else:
                raise AssertionError('Transactional projection error swallowed')
        assert q('SELECT count(*) FROM sensor_reading WHERE sensor_id=%s', (SENSOR,)) == [(0,)]
        checks['source_rollback_on_projection_failure'] = True
        held = q("SELECT id,available_at,event_key FROM clickhouse_outbox WHERE status IN ('pending','retryable')")
        assert all(row[2].startswith('kernel-recovery') for row in held)
        for row in held:
            q("UPDATE clickhouse_outbox SET available_at=NOW()+INTERVAL '1 day' WHERE id=%s", (row[0],))
        ids = []
        for minute, value in enumerate([10.12345, 20, 30]):
            clock = f'12:{minute:02}:00'
            rid = insert_reading(conn, info, DAY, clock, value)
            insert_reading_clickhouse(info, DAY, clock, value, conn=conn)
            conn.commit()
            ids.append(rid)
        assert insert_reading(conn, info, DAY, '12:00:00', 10.12345) == ids[0]
        insert_reading_clickhouse(info, DAY, '12:00:00', 10.12345, conn=conn)
        conn.commit()
        try:
            insert_reading(conn, info, DAY, '12:00:00', 99)
        except ValueError:
            conn.rollback()
        else:
            raise AssertionError('Conflicting source timestamp accepted')
        checks['source_and_outbox_duplicate_identity_preserved'] = True
        checks['conflicting_source_reading_rejected'] = True
        assert q("SELECT count(*) FROM clickhouse_outbox WHERE source_table='sensor_reading' AND source_id=ANY(%s)", (ids,)) == [(3,)]
        assert outbox.deliver_batch(conn, 'canonical-fixture-worker', 3) == {'claimed': 3, 'delivered': 3, 'failed': 0}
        pg = q('SELECT count(*),avg(value),min(value),max(value) FROM sensor_reading WHERE sensor_id=%s', (SENSOR,))[0]
        actual = sink.query("SELECT count(),avg(value),min(value),max(value) FROM sensor_readings WHERE sensor_id='%s'" % SENSOR).result_rows[0]
        assert actual[0] == pg[0] == 3 and all(abs(float(a)-float(b)) < 1e-9 for a,b in zip(actual[1:], pg[1:]))
        assert sink.query("SELECT DISTINCT unit FROM sensor_readings WHERE sensor_id='%s'" % SENSOR).result_rows == [('%',)]
        summary = sink.query("SELECT total_readings,avg_value,min_value,max_value FROM v_daily_sensor_summary_v3 WHERE day='2026-10-09' AND location_id='a0000000-0000-0000-0000-000000000001' AND sensor_type='soil_moisture'").result_rows[0]
        assert summary[0] == 3 and all(abs(float(a)-float(b)) < 1e-9 for a,b in zip(summary[1:], pg[1:]))
        checks['live_raw_and_v3_match_canonical_numeric_precision'] = True
        checks['canonical_unit_and_source_uuid_preserved'] = True
        print(json.dumps({'checks': checks, 'source_rows': 3, 'source_average': str(pg[1]), 'scope': 'Actual producer helpers, PostgreSQL source/outbox and live driver; no complete CSV/HTTP validation, event effects, device authorization or concurrency acceptance.'}))
    finally:
        conn.rollback()
        for row in held:
            q('UPDATE clickhouse_outbox SET available_at=%s WHERE id=%s', (row[1], row[0]))
        sink.close()
        conn.close()


if __name__ == '__main__':
    main()
