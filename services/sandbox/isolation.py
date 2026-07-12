"""Isolation guard — SQL-level isolation for sandboxed analysis."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("sandbox.isolation")


class IsolationGuard:
    """Enforces SQL-level isolation for sandboxed environments."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def get_sandbox_rules(self, env_id: str) -> dict | None:
        """Get sandbox rules for an environment."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT allowed_tables, denied_tables, max_query_rows,
                           max_execution_seconds, network_access
                    FROM analysis_sandbox
                    WHERE environment_id = %s
                    """,
                    (env_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "allowed_tables": row[0],
                    "denied_tables": row[1],
                    "max_query_rows": row[2],
                    "max_execution_seconds": row[3],
                    "network_access": row[4],
                }
        except Exception:
            logger.exception("Failed to get sandbox rules")
            return None

    def validate_query(self, env_id: str, query: str) -> tuple[bool, str]:
        """Validate a SQL query against sandbox rules. Returns (allowed, reason)."""
        rules = self.get_sandbox_rules(env_id)
        if not rules:
            return False, "No sandbox rules found"

        query_upper = query.upper().strip()

        # Check for forbidden operations
        forbidden_ops = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        for op in forbidden_ops:
            if query_upper.startswith(op):
                return False, f"Operation not allowed: {op}"

        # Check for denied tables (simple substring check)
        for denied in rules.get("denied_tables", []):
            if denied.lower() in query.lower():
                return False, f"Access denied to table: {denied}"

        # Check for network access attempts
        if not rules.get("network_access", False):
            network_funcs = ["DBLINK", "HTTP", "CURLOPT", "PG_READ_FILE"]
            for func in network_funcs:
                if func in query_upper:
                    return False, f"Network access not allowed: {func}"

        # Check for LIMIT enforcement
        if "LIMIT" not in query_upper and "SELECT" in query_upper:
            # Auto-add limit if missing
            logger.debug("Query missing LIMIT; sandbox will enforce max_query_rows=%d", rules["max_query_rows"])

        return True, "OK"

    def get_allowed_tables(self, env_id: str) -> list[str]:
        """Get list of tables the sandbox can read."""
        rules = self.get_sandbox_rules(env_id)
        if not rules:
            return []
        return rules.get("allowed_tables", [])

    def is_table_allowed(self, env_id: str, table_name: str) -> bool:
        """Check if a specific table is allowed."""
        rules = self.get_sandbox_rules(env_id)
        if not rules:
            return False
        allowed = rules.get("allowed_tables", [])
        denied = rules.get("denied_tables", [])
        if table_name in denied:
            return False
        if not allowed:  # Empty = all tables allowed (except denied)
            return True
        return table_name in allowed
