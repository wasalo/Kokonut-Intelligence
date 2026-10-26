"""Durable PostgreSQL-to-ClickHouse delivery.

PostgreSQL producers enqueue rows in their transaction. This module claims,
delivers, retries, and dead-letters those rows without losing the source event.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.common.cli import get_connection, print_json, run
from services.common.logging import get_logger
from services.ingestion.base import _validate_ch_identifiers, get_clickhouse

logger = get_logger("ingestion.clickhouse_outbox")

MAX_ATTEMPTS = 8
LEASE_SECONDS = 300
RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 3600

_PROJECTION_COLUMNS = {
    "attestation_events": frozenset({
        "timestamp", "attestation_uid", "schema_uid", "chain", "attester",
        "recipient", "subject_type", "status", "revoked", "metadata",
    }),
    "dlego_events": frozenset({
        "timestamp", "wallet_id", "protocol_id", "location_id", "action_type",
        "amount", "token", "chain", "tx_hash", "metadata",
    }),
    "remote_sensing_events": frozenset({
        "timestamp", "observation_id", "location_id", "plot_id", "source",
        "ndvi", "ndre", "evi", "savi", "canopy_cover_pct", "canopy_height_m",
        "ndwi", "cloud_cover_pct", "metadata", "msavi", "satvi", "bsi",
        "nbr2", "ndti", "lswi", "brightness_index", "tc_brightness",
        "tc_greenness", "tc_wetness", "band_blue", "band_green", "band_red",
        "band_nir", "band_swir1", "band_swir2", "source_system",
    }),
    "sensor_readings": frozenset({
        "timestamp", "sensor_id", "sensor_type", "location_id", "plot_id",
        "value", "unit", "quality", "metadata",
    }),
    "wallet_events": frozenset({
        "timestamp", "wallet_address", "chain", "tx_hash", "block_number",
        "event_type", "from_address", "to_address", "contract_address", "value",
        "token", "token_amount", "gas_used", "status", "metadata",
    }),
    "weather_events": frozenset({
        "timestamp", "location_id", "source", "temperature_c",
        "precipitation_mm", "humidity_pct", "wind_speed_kmh",
        "solar_radiation_wm2", "cloud_cover_pct", "metadata",
    }),
}
_REQUIRED_PROJECTION_COLUMNS = {
    "attestation_events": frozenset({"timestamp", "attestation_uid", "chain", "subject_type"}),
    "dlego_events": frozenset({"timestamp", "protocol_id", "chain", "action_type"}),
    "remote_sensing_events": frozenset({"timestamp", "observation_id", "location_id", "source"}),
    "sensor_readings": frozenset({"timestamp", "sensor_id", "location_id", "value"}),
    "wallet_events": frozenset({"timestamp", "wallet_address", "chain", "tx_hash", "event_type"}),
    "weather_events": frozenset({"timestamp", "location_id", "source"}),
}


class OutboxEnqueueError(RuntimeError):
    """A canonical source write could not be paired with its projection."""


def _retry_delay_seconds(attempt_count: int) -> int:
    """Return capped exponential delay after a failed delivery attempt."""
    if isinstance(attempt_count, bool) or not isinstance(attempt_count, int):
        raise ValueError("Outbox attempt count must be an integer")
    exponent = min(max(attempt_count - 1, 0), 6)
    return min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2**exponent))


def _validate_outbox_projection(row: dict[str, Any]) -> None:
    """Reject outbox payloads outside the repository-owned ClickHouse schema."""
    if not isinstance(row, dict):
        raise ValueError("projection row must be an object")
    table = row.get("target_table")
    allowed_columns = _PROJECTION_COLUMNS.get(table) if isinstance(table, str) else None
    if allowed_columns is None:
        raise ValueError("projection target is not allowlisted")

    columns = row.get("columns")
    if (
        not isinstance(columns, list)
        or not columns
        or any(not isinstance(column, str) for column in columns)
    ):
        raise ValueError("projection columns must be a non-empty string list")
    _validate_ch_identifiers(table, columns)
    if len(columns) != len(set(columns)):
        raise ValueError("projection columns must be unique")
    if not set(columns).issubset(allowed_columns):
        raise ValueError("projection columns are not allowed for this target")
    if not _REQUIRED_PROJECTION_COLUMNS[table].issubset(columns):
        raise ValueError("projection omits required identity columns")

    values = row.get("rows")
    if not isinstance(values, list) or not values:
        raise ValueError("projection must contain at least one row")
    if any(not isinstance(item, list) or len(item) != len(columns) for item in values):
        raise ValueError("projection row width differs from columns")


def enqueue(
    conn,
    *,
    event_key: str,
    source_table: str,
    source_id: str,
    target_table: str,
    columns: list[str],
    rows: list[list[Any]],
    payload_hash: str,
) -> str:
    """Insert one idempotent delivery record into the caller's transaction."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clickhouse_outbox
                    (event_key, source_table, source_id, target_table, columns, rows, payload_hash)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                ON CONFLICT (event_key) DO UPDATE SET updated_at = NOW()
                WHERE clickhouse_outbox.payload_hash = EXCLUDED.payload_hash
                  AND clickhouse_outbox.source_table = EXCLUDED.source_table
                  AND clickhouse_outbox.source_id = EXCLUDED.source_id
                  AND clickhouse_outbox.target_table = EXCLUDED.target_table
                  AND clickhouse_outbox.columns = EXCLUDED.columns
                  AND clickhouse_outbox.rows = EXCLUDED.rows
                RETURNING id
                """,
                (
                    event_key,
                    source_table,
                    source_id,
                    target_table,
                    json.dumps(columns),
                    json.dumps(rows, default=str),
                    payload_hash,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise OutboxEnqueueError("Outbox event key conflicts with an existing projection")
        return str(row[0])
    except OutboxEnqueueError:
        raise
    except Exception:
        raise OutboxEnqueueError("Could not enqueue the canonical ClickHouse projection") from None


def _recover_expired(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE clickhouse_outbox
            SET status = CASE WHEN attempt_count >= %s THEN 'dead_letter' ELSE 'retryable' END,
                lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
                available_at = NOW(), updated_at = NOW(),
                last_error = COALESCE(last_error, 'delivery lease expired')
            WHERE status = 'processing' AND lease_expires_at < NOW()
            """,
            (MAX_ATTEMPTS,),
        )


def claim_batch(conn, worker_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Claim a bounded batch and commit the lease before network I/O."""
    token = str(uuid.uuid4())
    _recover_expired(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT id FROM clickhouse_outbox
                WHERE status IN ('pending', 'retryable') AND available_at <= NOW()
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED LIMIT %s
            )
            UPDATE clickhouse_outbox o
            SET status = 'processing', attempt_count = attempt_count + 1,
                lease_owner = %s, lease_token = %s, lease_expires_at = %s,
                updated_at = NOW()
            FROM candidates c WHERE o.id = c.id
            RETURNING o.*
            """,
            (limit, worker_id, token, datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)),
        )
        rows = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
    conn.commit()
    return rows


def _finish(
    conn,
    row_id: str,
    worker_id: str,
    lease_token: str,
    *,
    success: bool,
    error: str | None = None,
    retry_delay_seconds: int = RETRY_BASE_SECONDS,
    permanent_failure: bool = False,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE clickhouse_outbox
            SET status = CASE WHEN %s THEN 'succeeded'
                              WHEN %s THEN 'dead_letter'
                              WHEN attempt_count >= %s THEN 'dead_letter'
                              ELSE 'retryable' END,
                available_at = CASE WHEN %s THEN available_at
                                    ELSE NOW() + (%s * INTERVAL '1 second') END,
                delivered_at = CASE WHEN %s THEN NOW() ELSE delivered_at END,
                last_error = %s, lease_owner = NULL, lease_token = NULL,
                lease_expires_at = NULL, updated_at = NOW()
            WHERE id = %s AND status = 'processing'
              AND lease_owner = %s AND lease_token = %s
              AND lease_expires_at > NOW()
            """,
            (success, permanent_failure, MAX_ATTEMPTS, success, retry_delay_seconds, success, error,
             row_id, worker_id, lease_token),
        )
        changed = cur.rowcount == 1
    conn.commit()
    return changed


def deliver_batch(conn, worker_id: str, limit: int = 100) -> dict[str, int]:
    """Deliver one claimed batch; each row has independent failure handling."""
    from services.core.providers import ProviderSettings

    if not ProviderSettings.from_environment().clickhouse:
        # Keep pending projections and retry budgets intact while paused.
        return {"claimed": 0, "delivered": 0, "failed": 0}

    rows = claim_batch(conn, worker_id, limit)
    if not rows:
        return {"claimed": 0, "delivered": 0, "failed": 0}
    valid_rows = []
    invalid_count = 0
    for row in rows:
        try:
            _validate_outbox_projection(row)
        except (TypeError, ValueError):
            logger.warning("ClickHouse outbox projection rejected (contract validation)")
            _finish(
                conn,
                str(row["id"]),
                worker_id,
                str(row["lease_token"]),
                success=False,
                error="projection contract rejected",
                permanent_failure=True,
            )
            invalid_count += 1
        else:
            valid_rows.append(row)
    if not valid_rows:
        return {"claimed": len(rows), "delivered": 0, "failed": invalid_count}

    delivered = failed = 0
    client = None
    try:
        try:
            client = get_clickhouse()
            if client is None:
                raise RuntimeError("ClickHouse client unavailable")
        except Exception as exc:
            logger.warning("ClickHouse client setup failed (%s)", type(exc).__name__)
            for row in valid_rows:
                _finish(conn, str(row["id"]), worker_id, str(row["lease_token"]),
                        success=False, error=f"client setup failed: {type(exc).__name__}",
                        retry_delay_seconds=_retry_delay_seconds(row.get("attempt_count", 1)))
            return {"claimed": len(rows), "delivered": 0, "failed": invalid_count + len(valid_rows)}
        for row in valid_rows:
            error = None
            inserted = False
            try:
                _validate_ch_identifiers(row["target_table"], row["columns"])
                if any(len(values) != len(row["columns"]) for values in row["rows"]):
                    raise ValueError("Outbox projection row width differs from columns")
                documents = []
                for values in row["rows"]:
                    document = dict(zip(row["columns"], values))
                    # Older sensor producers stored an empty nullable UUID.
                    if row["target_table"] == "sensor_readings" and document.get("plot_id") == "":
                        document["plot_id"] = None
                    documents.append(json.dumps(document, default=str))
                token = hashlib.sha256(row["event_key"].encode()).hexdigest()
                client.raw_insert(row["target_table"], column_names=row["columns"],
                                  insert_block="\n".join(documents).encode(), fmt="JSONEachRow",
                                  settings={"date_time_input_format": "best_effort",
                                            "insert_deduplicate": 1,
                                            "insert_deduplication_token": token})
                inserted = True
            except Exception as exc:
                logger.warning(
                    "ClickHouse outbox delivery failed for %s (%s)",
                    row["event_key"],
                    type(exc).__name__,
                )
                error = f"ClickHouse delivery failed ({type(exc).__name__})"
            # Database failure is not a transport failure. Let it propagate;
            # durable leases recover unfinished rows after expiry.
            ok = _finish(conn, str(row["id"]), worker_id, str(row["lease_token"]),
                         success=inserted, error=error,
                         retry_delay_seconds=_retry_delay_seconds(row.get("attempt_count", 1)))
            if inserted and ok:
                delivered += 1
            else:
                failed += 1
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()
    return {"claimed": len(rows), "delivered": delivered, "failed": invalid_count + failed}


def reconcile_pending(conn, limit: int = 1000) -> dict[str, int]:
    """Return durable delivery gaps that can be repaired by the normal worker."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE status IN ('pending', 'retryable')),
                   COUNT(*) FILTER (WHERE status = 'dead_letter'),
                   COUNT(*) FILTER (WHERE status = 'succeeded')
            FROM clickhouse_outbox
            """
        )
        pending, dead, succeeded = cur.fetchone()
    return {"pending": pending or 0, "dead_letter": dead or 0, "succeeded": succeeded or 0, "limit": limit}


def _operator_transition(conn, row_id: str, action: str, actor: str, reason: str) -> dict[str, Any]:
    if action not in {"replayed", "resolved", "discarded"}:
        raise ValueError("Unsupported outbox disposition")
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 255:
        raise ValueError("Operator actor must contain 1 to 255 characters")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
        raise ValueError("Operator reason must contain 1 to 2000 characters")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH eligible AS (
                    SELECT id, attempt_count FROM clickhouse_outbox
                    WHERE id = %s AND status = 'dead_letter' FOR UPDATE
                ), transitioned AS (
                    UPDATE clickhouse_outbox o
                    SET status = %s, attempt_count = CASE WHEN %s THEN 0 ELSE o.attempt_count END,
                        available_at = NOW(), updated_at = NOW(),
                        last_error = CASE WHEN %s THEN NULL ELSE o.last_error END,
                        lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL
                    FROM eligible e WHERE o.id = e.id AND o.status = 'dead_letter'
                    RETURNING o.id, o.event_key, o.payload_hash, e.attempt_count
                )
                INSERT INTO clickhouse_outbox_operator_audit
                    (outbox_id, event_key, action, actor, reason, prior_attempt_count, payload_hash)
                SELECT id, event_key, %s, %s, %s, attempt_count, payload_hash FROM transitioned
                RETURNING outbox_id, event_key
                """,
                (row_id, "pending" if action == "replayed" else action,
                 action == "replayed", action == "replayed", action, actor.strip(), reason.strip()),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if row is None:
        return {"status": "error", "message": "Outbox row is not dead-lettered"}
    return {"status": action, "id": str(row[0]), "event_key": row[1]}


def replay_dead_letter(conn, row_id: str, actor: str, reason: str) -> dict[str, Any]:
    """Re-enqueue once, retaining an audited operator identity and reason."""
    return _operator_transition(conn, row_id, "replayed", actor, reason)


def dispose_dead_letter(conn, row_id: str, disposition: str, actor: str, reason: str) -> dict[str, Any]:
    """Close a dead letter without deleting its source or projection payload."""
    if disposition not in {"resolved", "discarded"}:
        raise ValueError("Disposition must be resolved or discarded")
    return _operator_transition(conn, row_id, disposition, actor, reason)


def list_dead_letters(conn, limit: int = 50) -> list[dict[str, Any]]:
    """List dead-lettered rows for operator review."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, event_key, source_table, source_id, target_table,
                   attempt_count, last_error, created_at, updated_at
            FROM clickhouse_outbox
            WHERE status = 'dead_letter'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        results = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
    for result in results:
        if result.get("last_error") is not None:
            result["last_error"] = "[details redacted]"
    return results


def command(args):
    if not 1 <= args.limit <= 1000:
        raise ValueError("Limit must be between 1 and 1000")
    with get_connection() as conn:
        if args.replay_dead_letter:
            result = replay_dead_letter(conn, args.replay_dead_letter, args.actor, args.reason)
        elif args.dispose_dead_letter:
            result = dispose_dead_letter(conn, args.dispose_dead_letter, args.disposition, args.actor, args.reason)
        elif args.list_dead_letter:
            result = list_dead_letters(conn, args.limit)
        elif args.reconcile:
            result = reconcile_pending(conn, args.limit)
        else:
            result = deliver_batch(conn, args.worker_id, args.limit)
    print_json(result)
    if args.run_once and result.get("failed", 0):
        raise SystemExit(1)
    if (args.replay_dead_letter or args.dispose_dead_letter) and result.get("status") == "error":
        raise SystemExit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Deliver PostgreSQL-to-ClickHouse outbox rows")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-once", action="store_true")
    group.add_argument("--reconcile", action="store_true")
    group.add_argument("--list-dead-letter", action="store_true", help="List dead-lettered rows")
    group.add_argument("--replay-dead-letter", metavar="ROW_ID", help="Re-enqueue a dead-lettered row for retry")
    group.add_argument("--dispose-dead-letter", metavar="ROW_ID")
    parser.add_argument("--disposition", choices=["resolved", "discarded"])
    parser.add_argument("--actor", help="Required operator identity for replay/disposal")
    parser.add_argument("--reason", help="Required review reason for replay/disposal")
    parser.add_argument("--worker-id", default=f"clickhouse-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--limit", type=int, default=100)
    run(command, parser.parse_args())


if __name__ == "__main__":
    main()
