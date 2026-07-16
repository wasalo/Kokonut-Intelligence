"""Read-only governance cockpit projections."""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg2.extras


def _row(row: Any) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {key: (str(value) if hasattr(value, "hex") else value) for key, value in dict(row).items()}


def internal_cockpit(conn) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_governance_cockpit_internal")
        return _row(cur.fetchone()) or {}


def public_cockpit(conn) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_governance_cockpit_public")
        return _row(cur.fetchone()) or {}
