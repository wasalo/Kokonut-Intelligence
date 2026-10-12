"""Mutating operator-audit checks for the guarded isolated fixture only."""
import json

from services.common.database import get_db
from services.ingestion.clickhouse_outbox import dispose_dead_letter, enqueue, replay_dead_letter


def main():
    conn = get_db()
    checks = {}

    def q(sql, args=()):
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
        conn.commit()
        return rows

    try:
        assert q('SELECT current_database()') == [('kokonut_intelligence',)]
        assert q('SELECT count(*) FROM clickhouse_outbox_operator_audit') == [(0,)]
        ids = []
        for index in range(4):
            rid = enqueue(conn, event_key=f'kernel-recovery-audit:{index}',
                          source_table='synthetic_recovery', source_id=f'audit-{index}',
                          target_table='sensor_readings', columns=['value'], rows=[[index]],
                          payload_hash=str(index) * 64)
            conn.commit()
            q("UPDATE clickhouse_outbox SET status='dead_letter',attempt_count=8 WHERE id=%s", (rid,))
            ids.append(rid)
        for actor, reason in [('', 'reviewed'), ('operator', ''), ('x' * 256, 'reviewed')]:
            try:
                replay_dead_letter(conn, ids[0], actor, reason)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid audit identity accepted')
        checks['identity_reason_and_bounds_required'] = True
        for rid, action in zip(ids[:3], ['replayed', 'resolved', 'discarded']):
            def operate():
                if action == 'replayed':
                    return replay_dead_letter(conn, rid, ' synthetic-operator ', ' Reviewed fixture ')
                return dispose_dead_letter(conn, rid, action, ' synthetic-operator ', ' Reviewed fixture ')
            assert operate()['status'] == action
            assert operate()['status'] == 'error'
            audit = q('SELECT action,actor,reason,prior_attempt_count FROM clickhouse_outbox_operator_audit WHERE outbox_id=%s', (rid,))
            assert audit == [(action, 'synthetic-operator', 'Reviewed fixture', 8)]
            expected = ('pending', 0) if action == 'replayed' else (action, 8)
            assert q('SELECT status,attempt_count FROM clickhouse_outbox WHERE id=%s', (rid,)) == [expected]
        checks['replay_and_both_dispositions_audited_once'] = True
        checks['attempt_history_preserved_and_payload_retained'] = q('SELECT count(*) FROM clickhouse_outbox WHERE id=ANY(%s::uuid[]) AND rows IS NOT NULL', (ids,)) == [(4,)]
        q("""CREATE FUNCTION pg_temp.reject_fixture_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic audit storage failure'; END $$;
             CREATE TRIGGER kernel_fixture_reject_audit BEFORE INSERT ON clickhouse_outbox_operator_audit FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_fixture_audit();""")
        try:
            try:
                replay_dead_letter(conn, ids[3], 'synthetic-operator', 'Audit failure fixture')
            except Exception:
                pass
            else:
                raise AssertionError('Audit failure accepted')
            assert q('SELECT status,attempt_count FROM clickhouse_outbox WHERE id=%s', (ids[3],)) == [('dead_letter', 8)]
            assert q('SELECT count(*) FROM clickhouse_outbox_operator_audit WHERE outbox_id=%s', (ids[3],)) == [(0,)]
            checks['audit_failure_rolls_back_transition'] = True
        finally:
            q('DROP TRIGGER kernel_fixture_reject_audit ON clickhouse_outbox_operator_audit')
        print(json.dumps({'checks': checks, 'scope': 'Synthetic real PostgreSQL audited operator transitions; no authenticated gateway, role isolation, concurrency or sink deduplication acceptance.'}))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
