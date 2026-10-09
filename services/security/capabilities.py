"""Capability manager — zero-trust capability tokens for fine-grained authorization."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from services.common.logging import get_logger

logger = get_logger("security.capabilities")


class CapabilityManager:
    """Issue, verify, and revoke time-scoped capability tokens."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(
        self,
        holder: str,
        capabilities: list[dict],
        ttl_seconds: int = 43200,
        max_usage: int | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Issue a new capability token. Returns token + metadata.

        capabilities format:
        [{"resource": "harvest_event", "action": "write", "location_id": "UUID", "constraints": {"status": "draft"}}]
        """
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        token_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO capability_token
                        (id, token_hash, holder, capabilities, expires_at,
                         max_usage, created_by, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        token_id, token_hash, holder,
                        json.dumps(capabilities), expires_at,
                        max_usage, created_by,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
            conn.commit()
            logger.info("Issued capability token to %s (expires=%s)", holder, expires_at)
            return {
                "token": token,
                "token_id": token_id,
                "holder": holder,
                "capabilities": capabilities,
                "expires_at": expires_at.isoformat(),
                "max_usage": max_usage,
            }
        except Exception:
            conn.rollback()
            logger.exception("Failed to issue capability token")
            raise

    def verify(
        self,
        token: str,
        resource: str,
        action: str,
        location_id: str | None = None,
    ) -> dict | None:
        """Verify a token has the requested capability. Returns capability match or None.

        Uses an atomic UPDATE ... RETURNING to prevent TOCTOU races on
        max_usage: the usage_count is incremented only when the token is
        still valid and the limit has not been reached.
        """
        token_hash = self._hash_token(token)
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                # Step 1: fetch token metadata (read-only)
                cur.execute(
                    """
                    SELECT id, holder, capabilities, expires_at, max_usage, revoked
                    FROM capability_token
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                token_id, holder, capabilities, expires_at, max_usage, revoked = row

                # Check revoked
                if revoked:
                    logger.warning("Revoked token used: holder=%s", holder)
                    return None

                # Check expiration
                if expires_at < datetime.now(timezone.utc):
                    logger.warning("Expired token used: holder=%s", holder)
                    return None

                # Check capabilities
                caps = capabilities if isinstance(capabilities, list) else json.loads(capabilities)
                matched_cap = None
                for cap in caps:
                    if cap.get("resource") != resource:
                        continue
                    if cap.get("action") != action:
                        continue
                    # A location-scoped request must be authorized by a
                    # capability scoped to that exact location.
                    if location_id and cap.get("location_id") != location_id:
                        continue
                    matched_cap = cap
                    break

                if matched_cap is None:
                    return None

                # Step 2: atomic increment only when usage limit allows
                if max_usage:
                    cur.execute(
                        """
                        UPDATE capability_token
                        SET usage_count = usage_count + 1
                        WHERE id = %s
                          AND NOT revoked
                          AND expires_at > NOW()
                          AND usage_count < max_usage
                        RETURNING id
                        """,
                        (token_id,),
                    )
                    if not cur.fetchone():
                        logger.warning("Token usage limit reached or token became invalid: holder=%s", holder)
                        conn.commit()
                        return None
                else:
                    cur.execute(
                        "UPDATE capability_token SET usage_count = usage_count + 1 WHERE id = %s",
                        (token_id,),
                    )
                conn.commit()

                logger.info("Token verified: holder=%s resource=%s action=%s", holder, resource, action)
                return {"holder": holder, "capability": matched_cap, "token_id": str(token_id)}

            return None
        except Exception:
            conn.rollback()
            logger.exception("Token verification failed")
            return None

    def revoke(self, token_id: str) -> bool:
        """Revoke a capability token."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE capability_token
                    SET revoked = TRUE, revoked_at = NOW()
                    WHERE id = %s AND NOT revoked
                    RETURNING id
                    """,
                    (token_id,),
                )
                result = cur.fetchone()
            conn.commit()
            if result:
                logger.info("Revoked token: %s", token_id)
            return result is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to revoke token")
            return False

    def revoke_by_holder(self, holder: str) -> int:
        """Revoke all tokens for a holder. Returns count revoked."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE capability_token
                    SET revoked = TRUE, revoked_at = NOW()
                    WHERE holder = %s AND NOT revoked
                    """,
                    (holder,),
                )
                count = cur.rowcount
            conn.commit()
            logger.info("Revoked %d tokens for holder %s", count, holder)
            return count
        except Exception:
            conn.rollback()
            logger.exception("Failed to revoke tokens for holder")
            return 0

    def list_tokens(self, holder: str | None = None, active_only: bool = True) -> list[dict]:
        """List capability tokens."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if holder:
                conditions.append("holder = %s")
                params.append(holder)
            if active_only:
                conditions.append("NOT revoked AND expires_at > NOW()")

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, holder, capabilities, issued_at, expires_at,
                           max_usage, usage_count, revoked, created_by
                    FROM capability_token
                    {where}
                    ORDER BY issued_at DESC
                    """,
                    params,
                )
                return [
                    {
                        "token_id": str(r[0]),
                        "holder": r[1],
                        "capabilities": r[2],
                        "issued_at": r[3].isoformat() if r[3] else None,
                        "expires_at": r[4].isoformat() if r[4] else None,
                        "max_usage": r[5],
                        "usage_count": r[6],
                        "revoked": r[7],
                        "created_by": r[8],
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list tokens")
            return []
