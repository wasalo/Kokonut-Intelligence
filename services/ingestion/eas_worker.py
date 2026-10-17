"""Run scheduled EAS indexing through a dedicated global worker identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from typing import Any

from services.common.cli import print_json, run
from services.common.worker_database import get_worker_db
from services.core.features import is_enabled

from .eas_provider import (
    ATTESTATIONS_BY_RECIPIENT,
    EAS_ENDPOINTS,
)
from .eas_provider import (
    execute_eas_query as query_eas,
)

WORKER_KEY = "eas_indexer"


class EASWorkerPersistenceError(RuntimeError):
    """A bounded PostgreSQL operation failed and the entire run must stop."""


def _validated_replay_lookback(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("EAS replay lookback seconds must be a non-negative integer")
    return value


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _fetch_wallet_pages(
    connection,
    *,
    chain: str,
    wallet_id: str,
    recipient: str,
    cursor_time: int,
    replay_lookback_seconds: int = 0,
    sleep=time.sleep,
) -> tuple[int, int]:
    """Persist pages, optionally replaying a bounded interval before the cursor."""
    replay_lookback_seconds = _validated_replay_lookback(replay_lookback_seconds)
    offset = 0
    max_time = cursor_time
    scan_floor = max(0, cursor_time - replay_lookback_seconds)
    inserted = 0
    previous_attestation_time: int | None = None
    while True:
        response = query_eas(
            chain,
            ATTESTATIONS_BY_RECIPIENT,
            {
                "recipient": recipient,
                "after": offset,
            },
        )
        if not isinstance(response, dict):
            raise ValueError("EAS provider returned an invalid response")
        if "attestations" not in response:
            raise ValueError("EAS provider response is missing attestations")
        attestations = response["attestations"]
        if not isinstance(attestations, list) or len(attestations) > 100:
            raise ValueError("EAS provider returned an invalid page")
        if not attestations:
            break

        page = []
        reached_cursor = False
        for attestation in attestations:
            if not isinstance(attestation, dict):
                raise ValueError("EAS provider returned an invalid attestation")
            raw_attestation_time = attestation.get("time")
            if isinstance(raw_attestation_time, bool) or not isinstance(raw_attestation_time, (int, str)):
                raise ValueError("EAS attestation timestamp is invalid")
            if isinstance(raw_attestation_time, str) and not raw_attestation_time.isdigit():
                raise ValueError("EAS attestation timestamp is invalid")
            try:
                attestation_time = int(raw_attestation_time)
            except (ValueError, TypeError):
                raise ValueError("EAS attestation timestamp is invalid") from None
            if attestation_time < 0 or attestation_time > 253402300799:
                raise ValueError("EAS attestation timestamp is invalid")
            if previous_attestation_time is not None and attestation_time > previous_attestation_time:
                raise ValueError("EAS provider page is not ordered newest first")
            previous_attestation_time = attestation_time
            if attestation_time < scan_floor:
                # The provider query is ordered newest first. Once it reaches
                # records older than the inclusive scan floor, later pages
                # cannot contribute records in the requested range. The
                # default floor is the saved cursor; explicit lookback lets an
                # operator recover records indexed late below it.
                reached_cursor = True
                continue
            if reached_cursor:
                # The order check above should make this unreachable. Keep the
                # guard explicit so malformed pages can never add older rows.
                raise ValueError("EAS provider page is not ordered newest first")
            max_time = max(max_time, attestation_time)
            page.append(
                {
                    "attestation": attestation,
                    "payload_hash": _hash_payload(attestation),
                }
            )

        if page:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT kokonut_security.store_eas_indexer_page(%s, %s::uuid, %s::jsonb)",
                        (chain, wallet_id, json.dumps(page, default=str)),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError("EAS worker returned no page result")
                    inserted += int(row[0])
                connection.commit()
            except Exception as exc:
                connection.rollback()
                raise EASWorkerPersistenceError("EAS page could not be persisted atomically") from exc

        if reached_cursor:
            break
        offset += len(attestations)
        if len(attestations) < 100:
            break
        sleep(0.5)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.advance_eas_indexer_cursor(%s, %s::uuid, %s)",
                (chain, wallet_id, max_time),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("EAS worker returned no cursor result")
        connection.commit()
    except Exception as exc:
        connection.rollback()
        raise EASWorkerPersistenceError("EAS recipient cursor could not be advanced") from exc
    return inserted, max_time


def ingest(chain: str, replay_lookback_seconds: int = 0) -> dict[str, Any]:
    """Index active recipients for one chain without shared PostgreSQL access."""
    if chain not in EAS_ENDPOINTS:
        raise ValueError(f"Unsupported EAS chain: {chain}")
    replay_lookback_seconds = _validated_replay_lookback(replay_lookback_seconds)

    started = time.monotonic()
    connection = get_worker_db(WORKER_KEY)
    lock_acquired = False
    errors: list[str] = []
    total_inserted = 0
    recipients: list[tuple[str, str]] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.acquire_eas_indexer_chain_lock(%s)",
                (chain,),
            )
        connection.commit()
        lock_acquired = True

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT wallet_id::text, recipient_address FROM kokonut_security.list_eas_indexer_recipients(%s)",
                (chain,),
            )
            recipients = [(str(row[0]), str(row[1])) for row in cursor.fetchall()]
        connection.commit()

        for wallet_id, recipient in recipients:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT kokonut_security.read_eas_indexer_cursor(%s, %s::uuid)",
                    (chain, wallet_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("EAS worker returned no cursor value")
                cursor_time = int(row[0] or 0)
            connection.commit()
            try:
                inserted, _ = _fetch_wallet_pages(
                    connection,
                    chain=chain,
                    wallet_id=wallet_id,
                    recipient=recipient,
                    cursor_time=cursor_time,
                    replay_lookback_seconds=replay_lookback_seconds,
                )
                total_inserted += inserted
            except EASWorkerPersistenceError:
                raise
            except Exception as exc:
                connection.rollback()
                errors.append(f"{recipient[:10]}: {type(exc).__name__}: {str(exc)[:300]}")

        error_message = "; ".join(errors[:3])[:500] or None
        status = "error" if errors else "healthy"
        processing_time_ms = min(600_000, max(0, int((time.monotonic() - started) * 1000)))
        payload_hash = _hash_payload(
            {
                "chain": chain,
                "wallets": len(recipients),
                "replay_lookback_seconds": replay_lookback_seconds,
            }
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.finish_eas_indexer_chain(%s, %s, %s, %s, %s, %s)",
                (chain, status, error_message, total_inserted, processing_time_ms, payload_hash),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("EAS worker returned no completion watermark")
            watermark = int(row[0] or 0)
        connection.commit()
        if errors:
            raise RuntimeError(f"EAS indexing incomplete for chain {chain}: " + "; ".join(errors[:3]))
        return {
            "status": "success",
            "chain": chain,
            "wallets": len(recipients),
            "attestations_inserted": total_inserted,
            "last_attestation_time": watermark,
            "replay_lookback_seconds": replay_lookback_seconds,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        if lock_acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT kokonut_security.release_eas_indexer_chain_lock(%s)",
                        (chain,),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated EAS attestation indexing")
    parser.add_argument("--chain", required=True, choices=tuple(EAS_ENDPOINTS))
    parser.add_argument(
        "--replay-lookback-seconds",
        type=int,
        default=0,
        help="explicitly re-scan this many seconds before each recipient cursor",
    )
    args = parser.parse_args()
    if args.replay_lookback_seconds < 0:
        parser.error("--replay-lookback-seconds must be non-negative")
    if not is_enabled("isolated_eas_indexer_worker"):
        parser.error("isolated EAS indexer worker is disabled")
    print_json(ingest(args.chain, replay_lookback_seconds=args.replay_lookback_seconds))


if __name__ == "__main__":
    run(main)
