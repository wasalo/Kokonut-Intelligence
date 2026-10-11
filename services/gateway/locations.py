"""Public location reads restricted to the existing governed aggregate view."""

from __future__ import annotations

from functools import partial
from typing import Callable


def public_locations(location_id: str | None = None, *, connection_factory: Callable | None = None) -> list[dict]:
    if connection_factory is None:
        from services.common.database import get_db

        connection_factory = partial(get_db, connect_timeout=3)
    conn = connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")
            sql = "SELECT location_id, location_name, country, region, status FROM v_public_farm_summary"
            parameters = ()
            if location_id is not None:
                sql += " WHERE location_id = %s"
                parameters = (location_id,)
            sql += " ORDER BY location_name, location_id LIMIT 100"
            cur.execute(sql, parameters)
            return [
                {"id": str(row[0]), "name": row[1], "country": row[2], "region": row[3], "status": row[4]}
                for row in cur.fetchall()
            ]
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
