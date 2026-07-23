"""RACI responsibility assignments linking governed entities to parties."""

from __future__ import annotations

import uuid
from typing import Iterable, Mapping, Optional, Sequence

from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.common.database import get_db
from services.management.model import PARTY_TYPES, RACI_ROLES

logger = get_logger("management.responsibility")


def _conn_or(conn):
    if conn is not None:
        return conn, False
    return get_db(), True


def assign_responsibility(
    conn,
    entity_type: str,
    entity_id: str,
    party_type: str,
    party_id: str,
    raci_role: str,
) -> Mapping:
    """Assign a RACI responsibility. The DB enforces exactly one accountable party."""
    if party_type not in PARTY_TYPES:
        raise ValueError(f"invalid party_type: {party_type}")
    if raci_role not in RACI_ROLES:
        raise ValueError(f"invalid raci_role: {raci_role}")
    conn2, own = _conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO responsibility_assignment (
                    entity_type, entity_id, party_type, party_id, raci_role
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (entity_type, uuid.UUID(entity_id), party_type, uuid.UUID(party_id), raci_role),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    except IntegrityError as exc:
        conn2.rollback()
        if "uq_one_accountable" in str(exc):
            raise ValueError(
                f"entity {entity_type}:{entity_id} already has an accountable party"
            ) from exc
        raise
    finally:
        if own:
            conn2.close()


def list_responsibilities_for_entity(conn, entity_type: str, entity_id: str) -> Sequence[Mapping]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM responsibility_assignment
            WHERE entity_type = %s AND entity_id = %s
            ORDER BY raci_role, created_at
            """,
            (entity_type, uuid.UUID(entity_id)),
        )
        return cur.fetchall()


def get_accountable(conn, entity_type: str, entity_id: str) -> Optional[Mapping]:
    rows = list_responsibilities_for_entity(conn, entity_type, entity_id)
    for row in rows:
        if row["raci_role"] == "accountable":
            return row
    return None


def list_entities_for_party(conn, party_type: str, party_id: str) -> Sequence[Mapping]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM responsibility_assignment
            WHERE party_type = %s AND party_id = %s
            ORDER BY entity_type, created_at
            """,
            (party_type, uuid.UUID(party_id)),
        )
        return cur.fetchall()
