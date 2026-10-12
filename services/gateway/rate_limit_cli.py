"""Explicit operator maintenance for shared gateway throttle state."""

import argparse

from services.common.cli import get_connection, print_json, run


def cleanup_idle_buckets(limit: int = 1000) -> dict[str, int]:
    """Delete a bounded page idle over 24 hours, skipping in-use row locks.

    An idle bucket is already fully refilled under the fixed 100/10 policy.
    This command never resets a recently active caller's budget.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limit must be an integer between 1 and 1000")
    with get_connection(connect_timeout=3) as conn:
        conn.execute("SET LOCAL lock_timeout = '2s'")
        conn.execute("SET LOCAL statement_timeout = '3s'")
        row = conn.execute(
            """WITH candidates AS (
                   SELECT caller_hash FROM gateway_rate_bucket
                   WHERE updated_at < clock_timestamp() - INTERVAL '24 hours'
                   ORDER BY updated_at, caller_hash
                   FOR UPDATE SKIP LOCKED LIMIT :limit
               ), deleted AS (
                   DELETE FROM gateway_rate_bucket b USING candidates c
                   WHERE b.caller_hash = c.caller_hash RETURNING b.caller_hash
               ) SELECT COUNT(*) AS deleted FROM deleted""",
            {"limit": limit},
        ).first()
    return {"deleted": row["deleted"], "limit": limit, "idle_hours": 24}


def command(args):
    print_json(cleanup_idle_buckets(args.limit))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true", required=True,
                        help="Delete one bounded page of buckets idle for more than 24 hours")
    parser.add_argument("--limit", type=int, default=1000)
    run(command, parser.parse_args())


if __name__ == "__main__":
    main()
