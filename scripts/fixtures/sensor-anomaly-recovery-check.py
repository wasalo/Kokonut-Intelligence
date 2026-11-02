#!/usr/bin/env python3
"""Retired shared-identity EventBus crash-recovery fixture.

This historical fixture ran ``EventBus.process_pending()`` with the shared
application database identity. That dispatcher API has been removed. Do not
restore it or run this file against a candidate database. The maintained,
synthetic acceptance is
``scripts/check-sensor-anomaly-worker-delivery-disposable.py``, which uses the
migration-648 bounded dispatcher and dedicated event-dispatch login.
"""


def main() -> int:
    raise SystemExit(
        "This shared-identity recovery fixture is retired; use "
        "scripts/check-sensor-anomaly-worker-delivery-disposable.py"
    )


if __name__ == "__main__":
    main()
