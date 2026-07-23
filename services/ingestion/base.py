"""
Common Ingestion Utilities

Shared functions for all ingestion scripts: database connections,
logging, hashing, retry logic.
"""

import hashlib
import json
import random
import time
import functools
import re
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()

from ..common.logging import get_logger
from .config import (
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD,
    CH_HOST, CH_USER, CH_PASSWORD,
    RETRY_MAX_RETRIES, RETRY_BACKOFF, RETRY_JITTER,
)

logger = get_logger("ingestion.base")

_CH_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Transient exception types that warrant retry
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
)


def get_db():
    """Get PostgreSQL connection.

    Delegates to :func:`services.common.database.get_db` (the canonical
    connection factory) to ensure consistent connection parameters across
    all services.
    """
    from services.common.database import get_db as _canonical_get_db

    return _canonical_get_db()


def get_clickhouse():
    """Get ClickHouse HTTP connection."""
    try:
        import clickhouse_connect
        return clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD,
        )
    except ImportError:
        return None


def _validate_ch_identifiers(table: str, columns: list[str]) -> None:
    """Allow only static ClickHouse identifiers in generated SQL."""
    if not _CH_IDENTIFIER_RE.fullmatch(table) or any(
        not _CH_IDENTIFIER_RE.fullmatch(column) for column in columns
    ):
        raise ValueError("Invalid ClickHouse table or column identifier")


def insert_clickhouse_rows(table: str, columns: list[str], rows: list[list]) -> bool:
    """Insert rows through clickhouse-connect and always release the client."""
    if not rows:
        return True
    _validate_ch_identifiers(table, columns)
    client = get_clickhouse()
    if client is None:
        logger.warning("ClickHouse client unavailable — skipping %s insert", table)
        return False
    try:
        client.insert(table, rows, column_names=columns)
        return True
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


def post_clickhouse_rows(table: str, columns: list[str], rows: list[list]) -> bool:
    """Insert HTTP rows as JSONEachRow; values are never interpolated into SQL."""
    if not rows:
        return True
    _validate_ch_identifiers(table, columns)
    import requests
    from .config import CH_HOST, CH_PORT, CH_USER, CH_PASSWORD

    query = f"INSERT INTO {table} ({', '.join(columns)}) FORMAT JSONEachRow"
    payload = "\n".join(
        json.dumps(dict(zip(columns, row)), default=str) for row in rows
    )
    response = None
    try:
        response = requests.post(
            f"http://{CH_HOST}:{CH_PORT}",
            params={"query": query},
            data=payload.encode("utf-8"),
            auth=(CH_USER, CH_PASSWORD),
            headers={"Content-Type": "application/x-ndjson"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    finally:
        if response is not None:
            response.close()


def hash_payload(data: Any) -> str:
    """SHA-256 hash of raw payload for lineage tracking."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


INGESTION_PROCESSOR_VERSION = "1.0.0"


def log_ingestion(
    source_system: str,
    source_table: str,
    source_id: str,
    target_table: str,
    target_id: Optional[str],
    operation: str,
    payload_hash: str,
    status: str = "success",
    error_message: Optional[str] = None,
    rows_affected: int = 0,
    processing_time_ms: int = 0,
    processor_version: Optional[str] = None,
) -> None:
    """Log ingestion event to the ingestion_log table."""
    db = None
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_log
                    (source_system, source_table, source_id, target_table, target_id,
                     operation, payload_hash, status, error_message, rows_affected,
                     processing_time_ms, processor_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_system, source_table, source_id, target_table, target_id,
                    operation, payload_hash, status, error_message, rows_affected,
                    processing_time_ms, processor_version or INGESTION_PROCESSOR_VERSION,
                ),
            )
        db.commit()
    except Exception as e:
        logger.error("Failed to log ingestion: %s", e)
    finally:
        if db is not None:
            db.close()


def update_indexer_status(
    chain: str,
    indexer_type: str,
    last_synced_block: Optional[int] = None,
    status: str = "syncing",
    error_message: Optional[str] = None,
) -> None:
    """Update chain_indexer_status table."""
    db = None
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chain_indexer_status (chain, indexer_type, last_synced_block, last_synced_at, status, error_message)
                VALUES (%s, %s, %s, NOW(), %s, %s)
                ON CONFLICT (chain, indexer_type) DO UPDATE SET
                    last_synced_block = EXCLUDED.last_synced_block,
                    last_synced_at = NOW(),
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
                """,
                (chain, indexer_type, last_synced_block, status, error_message),
            )
        db.commit()
    except Exception as e:
        logger.error("Failed to update indexer status: %s", e)
    finally:
        if db is not None:
            db.close()


def get_last_synced_block(chain: str, indexer_type: str = "rpc") -> Optional[int]:
    """Get the last synced block for a chain."""
    db = None
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT last_synced_block FROM chain_indexer_status WHERE chain = %s AND indexer_type = %s",
                (chain, indexer_type),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        if db is not None:
            db.close()


def retry(
    max_retries: int = RETRY_MAX_RETRIES,
    backoff: float = RETRY_BACKOFF,
    jitter: float = RETRY_JITTER,
    exceptions=TRANSIENT_EXCEPTIONS,
):
    """Decorator with exponential backoff retry and jitter.

    Only retries on transient exceptions (network, timeout, connection errors).
    Permanent errors (ValueError, KeyError, etc.) propagate immediately.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = backoff * (2 ** attempt) + random.uniform(0, jitter)
                        logger.warning(
                            "Retry %d/%d for %s after %.1fs: %s",
                            attempt + 1, max_retries, func.__name__, wait, e,
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            "All %d retries exhausted for %s: %s",
                            max_retries, func.__name__, e,
                        )
            raise last_error
        return wrapper
    return decorator


def now_utc() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)
