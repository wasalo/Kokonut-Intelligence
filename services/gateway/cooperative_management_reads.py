"""Location-scoped aggregate reads for cooperative membership and shared assets."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {label} identifier") from exc


def _grouped_rows(cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_location_cooperative_management_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return location-scoped cooperative, membership, asset, and booking counts.

    Member identity, credential/KYC state, asset identifiers and serials,
    booking purpose/timing, financial amounts, GPS, notes, and metadata are
    intentionally excluded. Booking rows count only when both their asset and
    membership resolve through the same cooperative in this exact location.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="cooperative_management",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT CASE ct.name
                           WHEN 'marketing' THEN 'marketing'
                           WHEN 'input_purchase' THEN 'input_purchase'
                           WHEN 'equipment_sharing' THEN 'equipment_sharing'
                           WHEN 'processing' THEN 'processing'
                           ELSE 'other'
                       END AS cooperative_type,
                       c.status AS cooperative_status,
                       COUNT(DISTINCT c.id)::bigint AS cooperative_count,
                       COUNT(DISTINCT cm.id) FILTER (WHERE cm.status = 'active')
                           AS active_member_count
                  FROM cooperative AS c
                  JOIN cooperative_type AS ct ON ct.id = c.type_id
                  LEFT JOIN cooperative_membership AS cm
                    ON cm.cooperative_id = c.id
                   AND cm.location_id = %s::uuid
                 WHERE c.location_id = %s::uuid
                 GROUP BY 1, c.status
                 ORDER BY 1, c.status
                """,
                (location_id, location_id),
            )
            cooperatives = _grouped_rows(cursor)

            cursor.execute(
                """
                SELECT a.asset_type,
                       a.status AS asset_status,
                       COUNT(*)::bigint AS asset_count
                  FROM shared_asset AS a
                  JOIN cooperative AS c ON c.id = a.cooperative_id
                 WHERE c.location_id = %s::uuid
                   AND (a.location_id = %s::uuid OR a.location_id IS NULL)
                 GROUP BY a.asset_type, a.status
                 ORDER BY a.asset_type, a.status
                """,
                (location_id, location_id),
            )
            assets = _grouped_rows(cursor)

            cursor.execute(
                """
                SELECT b.status AS booking_status,
                       COUNT(*)::bigint AS booking_count
                  FROM asset_booking AS b
                  JOIN cooperative AS c
                    ON c.id = b.cooperative_id
                   AND c.location_id = %s::uuid
                  JOIN shared_asset AS a
                    ON a.id = b.asset_id
                   AND a.cooperative_id = c.id
                   AND (a.location_id = %s::uuid OR a.location_id IS NULL)
                  JOIN cooperative_membership AS cm
                    ON cm.id = b.membership_id
                   AND cm.cooperative_id = c.id
                   AND cm.location_id = %s::uuid
                 GROUP BY b.status
                 ORDER BY b.status
                """,
                (location_id, location_id, location_id),
            )
            bookings = _grouped_rows(cursor)

        return {
            "location_id": location_id,
            "cooperatives": cooperatives,
            "assets": assets,
            "bookings": bookings,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
