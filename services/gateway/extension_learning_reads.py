"""Location-scoped aggregate reads for extension learning and peer groups."""

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


def get_location_extension_learning_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded, aggregate-only extension-learning activity for a location.

    Queries never select learner identity, score values, free text, contact data,
    delivery errors, or arbitrary metadata. Peer membership joins repeat the
    authorized location so cross-location rows cannot affect the counts.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="extension_learning",
            action="read",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT em.category AS module_category, lp.status AS progress_status,
                       COUNT(*)::bigint AS enrollment_count
                  FROM learning_progress AS lp
                  JOIN extension_module AS em ON em.id = lp.module_id
                 WHERE lp.location_id = %s::uuid
                 GROUP BY em.category, lp.status
                 ORDER BY em.category, lp.status
                """,
                (location_id,),
            )
            learning_progress = _grouped_rows(cursor)

            cursor.execute(
                """
                SELECT delivery_channel, delivery_status,
                       COUNT(*)::bigint AS delivery_count
                  FROM content_delivery
                 WHERE location_id = %s::uuid
                 GROUP BY delivery_channel, delivery_status
                 ORDER BY delivery_channel, delivery_status
                """,
                (location_id,),
            )
            content_delivery = _grouped_rows(cursor)

            cursor.execute(
                """
                SELECT assessment_type, COUNT(*)::bigint AS assessment_count,
                       COUNT(score)::bigint AS scored_assessment_count
                  FROM skill_assessment
                 WHERE location_id = %s::uuid
                 GROUP BY assessment_type
                 ORDER BY assessment_type
                """,
                (location_id,),
            )
            assessments = _grouped_rows(cursor)

            cursor.execute(
                """
                SELECT pn.network_type, pn.status AS network_status,
                       COUNT(DISTINCT pn.id)::bigint AS network_count,
                       COUNT(pnm.id)::bigint AS active_member_count
                  FROM peer_network AS pn
                  LEFT JOIN peer_network_member AS pnm
                    ON pnm.network_id = pn.id
                   AND pnm.location_id = %s::uuid
                   AND pnm.status = 'active'
                   AND pnm.left_at IS NULL
                 WHERE pn.location_id = %s::uuid
                 GROUP BY pn.network_type, pn.status
                 ORDER BY pn.network_type, pn.status
                """,
                (location_id, location_id),
            )
            peer_networks = _grouped_rows(cursor)

        return {
            "location_id": location_id,
            "learning_progress": learning_progress,
            "content_delivery": content_delivery,
            "assessments": assessments,
            "peer_networks": peer_networks,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
