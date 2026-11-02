#!/usr/bin/env python3
"""Retired pre-migration-648 shared EventBus reconnect acceptance.

This historical harness started ``cmd_event_worker`` before migration 648 and
expected it to process events with the shared application login. Event worker
commands now require the default-off isolated dispatcher and deliberately
pause without opening that login. Its notification half likewise predates the
isolated notification-delivery and notification-enqueue identities. Replaying
the old fixture would test a removed privilege path, so this command refuses
to start Docker or touch a database.

Use ``scripts/check-event-dispatch-worker-disposable.py`` for the current
synthetic migration-648 bounded-function and login-boundary acceptance. A
process-level PostgreSQL stop/start harness remains open until it can launch
the migration-648 dispatcher after provisioning that login, without reviving
the shared dispatcher. Notification recovery is a separate worker acceptance.
"""


def main() -> int:
    raise SystemExit(
        "This shared-identity reconnect harness is retired; use "
        "scripts/check-event-dispatch-worker-disposable.py for current "
        "migration-648 acceptance"
    )


if __name__ == "__main__":
    main()
