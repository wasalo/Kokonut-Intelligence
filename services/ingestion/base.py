"""
Common Ingestion Utilities

Shared functions for all ingestion scripts: database connections,
logging, hashing, retry logic.
"""

import hashlib
import json
import time
import functools
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from .config import (
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD,
    CH_HOST, CH_USER, CH_PASSWORD,
)


def get_db():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def get_clickhouse():
    """Get ClickHouse HTTP connection."""
    try:
        import clickhouse_connect
        return clickhouse_connect.get_client(
            host=CH_HOST,
            port=8123,
            username=CH_USER,
            password=CH_PASSWORD,
        )
    except ImportError:
        return None


def hash_payload(data: Any) -> str:
    """SHA-256 hash of raw payload for lineage tracking."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


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
) -> None:
    """Log ingestion event to the ingestion_log table."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_log
                    (source_system, source_table, source_id, target_table, target_id,
                     operation, payload_hash, status, error_message, rows_affected, processing_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_system, source_table, source_id, target_table, target_id,
                    operation, payload_hash, status, error_message, rows_affected, processing_time_ms,
                ),
            )
        db.commit()
        db.close()
    except Exception as e:
        print(f"[Ingestion] Failed to log: {e}")


def update_indexer_status(
    chain: str,
    indexer_type: str,
    last_synced_block: Optional[int] = None,
    status: str = "syncing",
    error_message: Optional[str] = None,
) -> None:
    """Update chain_indexer_status table."""
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
        db.close()
    except Exception as e:
        print(f"[Ingestion] Failed to update indexer status: {e}")


def get_last_synced_block(chain: str, indexer_type: str = "rpc") -> Optional[int]:
    """Get the last synced block for a chain."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT last_synced_block FROM chain_indexer_status WHERE chain = %s AND indexer_type = %s",
                (chain, indexer_type),
            )
            row = cur.fetchone()
        db.close()
        return row[0] if row else None
    except Exception:
        return None


def retry(max_retries: int = 3, backoff: float = 2.0):
    """Decorator with exponential backoff retry."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = backoff ** attempt
                        print(f"[Ingestion] Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                        time.sleep(wait)
            raise last_error
        return wrapper
    return decorator


def now_utc() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)
