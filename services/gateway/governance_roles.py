"""Tenant-scoped aggregate reads for governance circles and coordination."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def get_location_governance_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded governance counts for one authorized location.

    Circle identifiers, names, and review state are included with role,
    assignment, authority, tension, and tactical counts. Person identities and
    all free-text tension, policy, session, and action content stay private.
    """
    try:
        operator_id = str(UUID(operator_id))
        location_id = str(UUID(location_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid operator or location identifier") from exc

    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL lock_timeout = '2s'")

        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action="read",
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.circle_key, c.name, c.status, c.review_due_at,
                       COUNT(DISTINCT r.id) FILTER (
                           WHERE r.status IN ('approved', 'active')
                       ) AS active_role_count,
                       COUNT(DISTINCT r.id) FILTER (
                           WHERE r.status IN ('approved', 'active')
                             AND r.review_due_at < NOW()
                       ) AS overdue_role_review_count,
                       COUNT(DISTINCT a.id) FILTER (
                           WHERE a.status = 'active'
                       ) AS active_assignment_count,
                       COUNT(DISTINCT a.id) FILTER (
                           WHERE a.status = 'proposed'
                       ) AS proposed_assignment_count,
                       COUNT(DISTINCT d.id) AS active_authority_domain_count
                  FROM governance_circle c
                  LEFT JOIN governance_role r ON r.circle_id = c.id
                  LEFT JOIN governance_role_assignment a ON a.role_id = r.id
                  LEFT JOIN governance_role_domain d
                    ON d.role_id = r.id
                   AND d.scope_type = 'location'
                   AND d.scope_id = %s::uuid
                   AND d.status = 'active'
                 WHERE c.scope_type = 'location'
                   AND c.scope_id = %s::uuid
                 GROUP BY c.id
                 ORDER BY c.circle_key
                """,
                (location_id, location_id),
            )
            circles = cur.fetchall()

            cur.execute(
                """
                SELECT COUNT(*) AS total_tensions,
                       COUNT(*) FILTER (
                           WHERE status IN ('submitted', 'triaged', 'in_progress', 'deferred')
                       ) AS unresolved_tensions,
                       COUNT(*) FILTER (
                           WHERE severity >= 4
                             AND status IN ('submitted', 'triaged', 'in_progress', 'deferred')
                       ) AS high_severity_unresolved_tensions,
                       COUNT(*) FILTER (
                           WHERE review_due_at < NOW()
                             AND status IN ('submitted', 'triaged', 'in_progress', 'deferred')
                       ) AS overdue_tension_reviews
                  FROM governance_tension
                 WHERE scope_type = 'location'
                   AND scope_id = %s::uuid
                """,
                (location_id,),
            )
            tensions = cur.fetchone()

            cur.execute(
                """
                SELECT COUNT(DISTINCT s.id) AS session_count,
                       COUNT(i.id) FILTER (
                           WHERE i.status IN ('open', 'in_progress')
                       ) AS open_item_count,
                       COUNT(i.id) FILTER (
                           WHERE i.status IN ('open', 'in_progress')
                             AND i.due_at < NOW()
                       ) AS overdue_item_count,
                       COUNT(i.id) FILTER (
                           WHERE i.status = 'disposed'
                       ) AS disposed_item_count
                  FROM governance_circle c
                  JOIN governance_tactical_session s ON s.circle_id = c.id
                  LEFT JOIN governance_tactical_item i ON i.session_id = s.id
                 WHERE c.scope_type = 'location'
                   AND c.scope_id = %s::uuid
                """,
                (location_id,),
            )
            tactical = cur.fetchone()

        return {
            "location_id": location_id,
            "circles": [
                {
                    "id": row[0],
                    "circle_key": row[1],
                    "name": row[2],
                    "status": row[3],
                    "review_due_at": row[4],
                    "active_role_count": row[5] or 0,
                    "overdue_role_review_count": row[6] or 0,
                    "active_assignment_count": row[7] or 0,
                    "proposed_assignment_count": row[8] or 0,
                    "active_authority_domain_count": row[9] or 0,
                }
                for row in circles
            ],
            "tensions": {
                "total": tensions[0] or 0,
                "unresolved": tensions[1] or 0,
                "high_severity_unresolved": tensions[2] or 0,
                "overdue_reviews": tensions[3] or 0,
            },
            "tactical": {
                "sessions": tactical[0] or 0,
                "open_items": tactical[1] or 0,
                "overdue_items": tactical[2] or 0,
                "disposed_items": tactical[3] or 0,
            },
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
