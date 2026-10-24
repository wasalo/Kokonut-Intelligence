"""Location-scoped read projections for produce traceability."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MAX_OFFSET = 10_000
_RELATED_LIMIT = 100
_BATCH_STATUSES = frozenset(
    {"active", "in_transit", "delivered", "consumed", "rejected", "expired"}
)


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {field} identifier") from exc


def _page(limit: int, offset: int) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_OFFSET:
        raise ValueError(f"offset must be between 0 and {_MAX_OFFSET}")
    return limit, offset


def _set_read_context(conn, operator_id: str, location_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL lock_timeout = '2s'")
    set_operator_tenant_context(
        conn,
        operator_id=operator_id,
        location_id=location_id,
        resource="traceability",
        action="read",
    )


def list_location_traceability_batches(
    operator_id: str,
    location_id: str,
    *,
    status: str | None = None,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List a bounded batch page using the caller's exact location grant."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    limit, offset = _page(limit, offset)
    if status is not None and status not in _BATCH_STATUSES:
        raise ValueError("Unsupported batch status")

    conn = (connection_factory or _connection_factory())()
    try:
        _set_read_context(conn, operator_id, location_id)
        with conn.cursor() as cur:
            if status is None:
                cur.execute(
                    """
                    SELECT id, batch_number, crop_name, variety, quantity_kg AS quantity,
                           quantity_unit AS unit, harvest_date, organic, status, created_at
                      FROM produce_batch
                     WHERE location_id = %s::uuid
                     ORDER BY harvest_date DESC, id
                     LIMIT %s OFFSET %s
                    """,
                    (location_id, limit + 1, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, batch_number, crop_name, variety, quantity_kg AS quantity,
                           quantity_unit AS unit, harvest_date, organic, status, created_at
                      FROM produce_batch
                     WHERE location_id = %s::uuid AND status = %s
                     ORDER BY harvest_date DESC, id
                     LIMIT %s OFFSET %s
                    """,
                    (location_id, status, limit + 1, offset),
                )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        return {
            "location_id": location_id,
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def get_location_traceability_batch(
    operator_id: str,
    location_id: str,
    batch_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Return a privacy-bounded trace and quality projection for one batch.

    Actor names, contact-like identifiers, free text, GPS, source references,
    evidence URLs, and arbitrary JSON payloads are deliberately not selected.
    Each related query independently proves that the batch belongs to the
    requested location.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    batch_id = _uuid(batch_id, "batch")
    conn = (connection_factory or _connection_factory())()
    try:
        _set_read_context(conn, operator_id, location_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, batch_number, crop_name, variety, quantity_kg AS quantity,
                       quantity_unit AS unit, harvest_date, organic, status,
                       expiry_date, grade
                  FROM produce_batch
                 WHERE id = %s::uuid AND location_id = %s::uuid
                """,
                (batch_id, location_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            batch = dict(zip((column[0] for column in cur.description), row))

            cur.execute(
                """
                SELECT sequence_num, from_actor_type, to_actor_type, transfer_date,
                       received_date, quantity_kg AS quantity, quantity_unit AS unit,
                       transfer_method, temperature_at_transfer_c, status
                  FROM chain_of_custody
                 WHERE batch_id = %s::uuid
                   AND EXISTS (
                       SELECT 1 FROM produce_batch pb
                        WHERE pb.id = chain_of_custody.batch_id
                          AND pb.location_id = %s::uuid
                   )
                 ORDER BY sequence_num
                 LIMIT %s
                """,
                (batch_id, location_id, _RELATED_LIMIT + 1),
            )
            custody = _fetch_related_rows(cur)
            cur.execute(
                """
                SELECT inspection_date, inspection_point, overall_grade, score,
                       moisture_pct, foreign_material_pct, temperature_c,
                       appearance_score, freshness_score, size_uniformity,
                       defect_count, passed, status
                  FROM quality_inspection
                 WHERE batch_id = %s::uuid
                   AND EXISTS (
                       SELECT 1 FROM produce_batch pb
                        WHERE pb.id = quality_inspection.batch_id
                          AND pb.location_id = %s::uuid
                   )
                 ORDER BY inspection_date, id
                 LIMIT %s
                """,
                (batch_id, location_id, _RELATED_LIMIT + 1),
            )
            quality = _fetch_related_rows(cur)
            cur.execute(
                """
                SELECT ct.name AS certification, ct.category, cv.issued_date,
                       cv.expiry_date, cv.verified, cv.chain_verified, cv.status
                  FROM certification_verify cv
                  JOIN certification_type ct ON ct.id = cv.certification_type_id
                 WHERE cv.batch_id = %s::uuid AND cv.location_id = %s::uuid
                 ORDER BY cv.issued_date, ct.name
                 LIMIT %s
                """,
                (batch_id, location_id, _RELATED_LIMIT + 1),
            )
            certification = _fetch_related_rows(cur)
            cur.execute(
                """
                SELECT record_type, record_time, temperature_c, temperature_min_c,
                       temperature_max_c, within_range, humidity_pct, ph_level,
                       hygiene_score, hand_wash_ok, protective_gear_ok,
                       pest_detected, passed, status
                  FROM food_safety_record
                 WHERE batch_id = %s::uuid
                   AND EXISTS (
                       SELECT 1 FROM produce_batch pb
                        WHERE pb.id = food_safety_record.batch_id
                          AND pb.location_id = %s::uuid
                   )
                 ORDER BY record_time, id
                 LIMIT %s
                """,
                (batch_id, location_id, _RELATED_LIMIT + 1),
            )
            food_safety = _fetch_related_rows(cur)
            cur.execute(
                """
                SELECT event_type, event_time, chain_verified, status
                  FROM provenance_event
                 WHERE batch_id = %s::uuid
                   AND EXISTS (
                       SELECT 1 FROM produce_batch pb
                        WHERE pb.id = provenance_event.batch_id
                          AND pb.location_id = %s::uuid
                   )
                 ORDER BY event_time, id
                 LIMIT %s
                """,
                (batch_id, location_id, _RELATED_LIMIT + 1),
            )
            provenance = _fetch_related_rows(cur)

        return {
            "location_id": location_id,
            "batch": batch,
            "custody_transfers": custody,
            "quality_inspections": quality,
            "certifications": certification,
            "food_safety_records": food_safety,
            "provenance_events": provenance,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _fetch_related_rows(cur) -> dict:
    columns = [column[0] for column in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return {"items": rows[:_RELATED_LIMIT], "truncated": len(rows) > _RELATED_LIMIT}
