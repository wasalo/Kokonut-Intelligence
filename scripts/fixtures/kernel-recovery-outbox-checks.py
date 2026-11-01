"""Isolated PostgreSQL outbox checks with controlled transport outcomes only."""
import json
import os
from unittest.mock import patch

from services.common.database import get_db
from services.common.worker_database import get_worker_db
from services.ingestion import clickhouse_outbox as outbox
from services.ingestion import clickhouse_outbox_worker as worker


def claim(worker_id, limit=1):
    connection = get_worker_db("clickhouse_outbox")
    try:
        return worker._claim(connection, worker_id, limit)
    finally:
        connection.close()


def finish(worker_id, row, **kwargs):
    connection = get_worker_db("clickhouse_outbox")
    try:
        return worker._finish(connection, worker_id, row, **kwargs)
    finally:
        connection.close()


def main():
    conn = get_db()
    checks = {}

    def read(sql, args=()):
        with conn.cursor() as cur:
            cur.execute(sql, args)
            result = cur.fetchall() if cur.description else []
        conn.commit()
        return result

    payload = dict(
        event_key='kernel-recovery-outbox:1',
        source_table='synthetic_recovery',
        source_id='fixture-1',
        target_table='sensor_readings',
        columns=['timestamp', 'sensor_id', 'location_id', 'value'],
        rows=[['2026-10-30T12:00:00Z', 'fixture-sensor', 'fixture-location', 12.5]],
        payload_hash='a' * 64,
    )
    try:
        assert read('SELECT current_database()') == [('kokonut_intelligence',)]
        assert read('SELECT count(*) FROM clickhouse_outbox') == [(0,)]
        outbox.enqueue(conn, **payload)
        conn.rollback()
        assert read('SELECT count(*) FROM clickhouse_outbox') == [(0,)]
        checks['enqueue_rollback_atomicity'] = True
        row_id = outbox.enqueue(conn, **payload)
        conn.commit()
        assert outbox.enqueue(conn, **payload) == row_id
        conn.commit()
        for changed in [dict(payload, payload_hash='b' * 64), dict(payload, rows=[[99]])]:
            try:
                outbox.enqueue(conn, **changed)
            except ValueError:
                conn.rollback()
            else:
                raise AssertionError('Conflicting projection accepted')
        checks['same_key_idempotency_and_conflicting_payload_rejection'] = True
        os.environ['KOKONUT_FEATURE_CLICKHOUSE'] = 'false'
        assert worker.run_once('fixture-worker') == {'claimed': 0, 'delivered': 0, 'failed': 0}
        assert read('SELECT attempt_count FROM clickhouse_outbox') == [(0,)]
        checks['disabled_provider_preserves_retry_budget'] = True
        claimed = claim('former-owner', 1)[0]
        read("UPDATE clickhouse_outbox SET lease_expires_at=NOW()-INTERVAL '1 second' WHERE id=%s", (row_id,))
        assert not finish('former-owner', claimed, success=True, error=None)
        reclaimed = claim('new-owner', 1)[0]
        assert reclaimed['attempt_count'] == 2
        assert not finish('former-owner', claimed, success=True, error=None)
        assert finish(
            'new-owner', reclaimed, success=False,
            error='Synthetic unavailable transport',
        )
        checks['expired_lease_and_stale_completion_rejected'] = True
        os.environ['KOKONUT_FEATURE_CLICKHOUSE'] = 'true'
        with patch.object(outbox, 'get_clickhouse', return_value=None):
            for _ in range(16):
                status, _attempts = read(
                    'SELECT status,attempt_count FROM clickhouse_outbox WHERE id=%s',
                    (row_id,),
                )[0]
                if status == 'dead_letter':
                    break
                read('UPDATE clickhouse_outbox SET available_at=NOW() WHERE id=%s', (row_id,))
                assert worker.run_once('fixture-worker', 1) == {
                    'claimed': 1, 'delivered': 0, 'failed': 1,
                }
            else:
                raise AssertionError('Bounded retry policy did not dead-letter the row')
        assert read('SELECT status,attempt_count FROM clickhouse_outbox') == [('dead_letter', 8)]
        checks['unavailable_transport_reaches_bounded_dead_letter'] = True
        assert outbox.replay_dead_letter(conn, row_id, 'synthetic-operator', 'Recovery fixture reviewed')['status'] == 'replayed'
        assert outbox.replay_dead_letter(conn, row_id, 'synthetic-operator', 'Recovery fixture reviewed')['status'] == 'error'
        checks['replay_and_duplicate_rejection'] = True
        sink = []

        class ControlledClient:
            def raw_insert(self, table, column_names, insert_block, fmt, settings):
                sink.append((table, insert_block, column_names))

            def close(self):
                pass

        with patch.object(outbox, 'get_clickhouse', return_value=ControlledClient()):
            assert worker.run_once('fixture-worker', 1) == {'claimed': 1, 'delivered': 1, 'failed': 0}
            assert worker.run_once('fixture-worker', 1) == {'claimed': 0, 'delivered': 0, 'failed': 0}
        assert len(sink) == 1
        assert read('SELECT status,attempt_count FROM clickhouse_outbox') == [('succeeded', 1)]
        checks['successful_delivery_not_reclaimed'] = True

        failure_payload = dict(payload, event_key='kernel-recovery-outbox:cli-failure', source_id='cli-failure')
        failure_id = outbox.enqueue(conn, **failure_payload)
        conn.commit()
        os.environ['KOKONUT_FEATURE_CLICKHOUSE'] = 'true'
        with patch.object(outbox, 'get_clickhouse', return_value=None):
            failure_result = worker.run_once('fixture-cli-failure', 1)
        assert failure_result == {'claimed': 1, 'delivered': 0, 'failed': 1}
        assert read('SELECT status,attempt_count FROM clickhouse_outbox WHERE id=%s', (failure_id,)) == [('retryable', 1)]
        checks['isolated_worker_failure_and_durable_retry'] = True

        success_payload = dict(payload, event_key='kernel-recovery-outbox:cli-success', source_id='cli-success')
        success_id = outbox.enqueue(conn, **success_payload)
        conn.commit()
        with patch.object(outbox, 'get_clickhouse', return_value=ControlledClient()):
            success_result = worker.run_once('fixture-cli-success', 1)
        assert success_result == {'claimed': 1, 'delivered': 1, 'failed': 0}
        assert read('SELECT status,attempt_count FROM clickhouse_outbox WHERE id=%s', (success_id,)) == [('succeeded', 1)]
        checks['isolated_worker_success_and_durable_delivery'] = True
        print(json.dumps({'checks': checks, 'scope': 'Real PostgreSQL, controlled unavailable/successful transport. No live ClickHouse driver, cross-store crash deduplication or operator replay audit acceptance.'}))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
