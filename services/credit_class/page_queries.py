"""Shared bounded database paging for credit-class list queries."""

from __future__ import annotations


def fetch_page(
    conn,
    *,
    count_sql: str,
    select_sql: str,
    params: dict,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Fetch a bounded, deterministically ordered result page and its total."""
    count_row = conn.execute(conn.text(count_sql), params).mappings().first()
    total = int(count_row["total"]) if count_row else 0

    page_params = {
        **params,
        "_page_limit": limit,
        "_page_offset": offset,
    }
    rows = conn.execute(conn.text(select_sql), page_params).mappings()
    return [dict(row) for row in rows], total
