"""Synthetic event recovery checks; run only through the guarded fixture operator.

Handler invocation is replaced with deterministic outcomes. This verifies durable
state transitions, not real handler effects, child-process timeouts or concurrency.
The database fixture is deliberately mutated; retain its checkpoint first.
"""

import json
from unittest.mock import patch

from services.common.database import get_db
from services.events.bus import EventBus

EVENT = 'f0000000-0000-4000-8000-000000000005'
ORPHAN = 'f0000000-0000-4000-8000-000000000009'
SUCCESS = 'f0000000-0000-4000-8000-000000000006'
ERROR = 'f0000000-0000-4000-8000-000000000007'
ACTOR = 'synthetic-recovery-operator'


def main():
    conn = get_db()
    bus = EventBus(conn=conn)
    checks = {}

    def read(sql, params=()):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return rows

    try:
        # Host launcher additionally checks Compose identity, volume and network.
        assert read('SELECT current_database()')[0][0] == 'kokonut_intelligence'
        assert read('SELECT count(*) FROM platform_event')[0][0] == 1
        assert read('SELECT event_type,status FROM platform_event WHERE id=%s', (EVENT,)) == [('kernel_recovery_fixture', 'processing')]
        assert read('SELECT count(*) FROM scheduled_task WHERE is_enabled')[0][0] == 0
        assert read("SELECT count(*) FROM event_handler WHERE is_enabled AND event_type='kernel_recovery_fixture'")[0][0] == 0
        assert not bus.replay_dead_letter(ORPHAN, ACTOR)
        checks['orphan_replay_rejected'] = True
        for operation in [lambda: bus.replay_dead_letter(EVENT, ''),
                          lambda: bus.dispose_dead_letter(ORPHAN, 'discarded', ACTOR, '')]:
            try:
                operation()
            except ValueError:
                pass
            else:
                raise AssertionError('Missing operator identity/reason accepted')
        checks['operator_identity_and_reason_required'] = True
        claimed = bus._claim(1, 'synthetic-recovery-worker')
        assert len(claimed) == 1 and str(claimed[0][0]) == EVENT
        assert not bus._complete(EVENT, 'fixture-former-worker')
        checks['expired_lease_reclaimed_and_stale_owner_rejected'] = True
        with conn.cursor() as cur:
            cur.execute('UPDATE event_handler SET is_enabled=true WHERE id IN (%s,%s)', (SUCCESS, ERROR))
        conn.commit()
        with patch.object(bus, '_invoke_handler', return_value=('error', 'Synthetic bounded failure')) as invoke:
            assert bus._process_event(EVENT, 'kernel_recovery_fixture', {}, 'synthetic-recovery-worker') == 'failed'
            assert invoke.call_count == 1
        assert read('SELECT attempt_count FROM event_handler_delivery WHERE event_id=%s AND handler_id=%s', (EVENT, SUCCESS)) == [(1,)]
        checks['successful_delivery_skipped_on_retry'] = True
        bus._retry_or_dead_letter(EVENT, 2, 3, 'synthetic-recovery-worker')
        assert read('SELECT status,retry_count FROM platform_event WHERE id=%s', (EVENT,)) == [('pending', 2)]
        assert len(bus._claim(1, 'synthetic-recovery-worker')) == 1
        with patch.object(bus, '_invoke_handler', return_value=('error', 'Synthetic bounded failure')):
            assert bus._process_event(EVENT, 'kernel_recovery_fixture', {}, 'synthetic-recovery-worker') == 'failed'
        bus._retry_or_dead_letter(EVENT, 3, 3, 'synthetic-recovery-worker')
        assert read('SELECT status,retry_count FROM platform_event WHERE id=%s', (EVENT,)) == [('dead_letter', 3)]
        checks['bounded_retry_reaches_durable_dead_letter'] = True
        assert bus.replay_dead_letter(EVENT, ACTOR)
        assert not bus.replay_dead_letter(EVENT, ACTOR)
        assert read("SELECT disposed_by,disposition FROM event_dead_letter WHERE original_event_id=%s", (EVENT,)) == [(ACTOR, 'replayed')]
        checks['replay_audited_and_duplicate_rejected'] = True
        assert len(bus._claim(1, 'synthetic-recovery-worker')) == 1
        with patch.object(bus, '_invoke_handler', return_value=('success', None)) as invoke:
            assert bus._process_event(EVENT, 'kernel_recovery_fixture', {}, 'synthetic-recovery-worker') == 'success'
            assert invoke.call_count == 1
        assert read('SELECT attempt_count,status FROM event_handler_delivery WHERE event_id=%s AND handler_id=%s', (EVENT, SUCCESS)) == [(1, 'success')]
        checks['replay_preserves_successful_delivery'] = True
        assert bus.dispose_dead_letter(ORPHAN, 'discarded', ACTOR, 'Synthetic orphan fixture reviewed')
        assert not bus.dispose_dead_letter(ORPHAN, 'discarded', ACTOR, 'Duplicate review')
        assert read('SELECT disposition,disposed_by,disposition_reason FROM event_dead_letter WHERE original_event_id=%s', (ORPHAN,)) == [('discarded', ACTOR, 'Synthetic orphan fixture reviewed')]
        checks['disposal_audited_and_duplicate_rejected'] = True
        print(json.dumps({'checks': checks, 'scope': 'Real PostgreSQL durable state; controlled handler outcomes; no domain effects, timeout or concurrency certification.'}))
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute('UPDATE event_handler SET is_enabled=false WHERE id IN (%s,%s)', (SUCCESS, ERROR))
        conn.commit()
        conn.close()


if __name__ == '__main__':
    main()
