"""Performance management (Balanced Scorecard / MbO) service."""

from __future__ import annotations

import uuid
from typing import Mapping, Optional, Sequence, Tuple

from psycopg2.extras import RealDictCursor

from services.common.logging import get_logger
from services.ingestion.base import get_db
from services.planning import model
from services.workflow_specs.objective import OBJECTIVE

logger = get_logger("planning.performance")


def assign_kpi(
    conn,
    objective_id: str,
    target_value,
    direction: str = "gte",
    metric_key: Optional[str] = None,
    metric_definition_id: Optional[str] = None,
    crisp_dimension: Optional[str] = None,
    current_value_snapshot=None,
    source_ref: Optional[str] = None,
) -> Mapping:
    conn2, own = model._conn_or(conn)
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO objective_kpi (
                    objective_id, metric_key, metric_definition_id, crisp_dimension,
                    target_value, direction, current_value_snapshot, source_ref
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    uuid.UUID(objective_id), metric_key,
                    uuid.UUID(metric_definition_id) if metric_definition_id else None,
                    crisp_dimension, target_value, direction,
                    current_value_snapshot, source_ref,
                ),
            )
            row = cur.fetchone()
            conn2.commit()
            return row
    finally:
        if own:
            conn2.close()


def list_kpis(conn, objective_id: str) -> Sequence[Mapping]:
    return model._rows(conn, "SELECT * FROM objective_kpi WHERE objective_id = %s", (uuid.UUID(objective_id),))


def record_review(
    conn,
    objective_id: str,
    reviewer_type: str,
    status: str,
    reviewer_id: Optional[str] = None,
    notes: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> Tuple[Mapping, Optional[str]]:
    """Record a review, advance objective.review_status, and (if off_track) spawn a corrective work item."""
    if status not in model.OBJECTIVE_REVIEW_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    conn2, own = model._conn_or(conn)
    corrective_work_item_id = None
    try:
        with conn2.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM objective WHERE id = %s FOR UPDATE", (uuid.UUID(objective_id),))
            obj = cur.fetchone()
            if not obj:
                raise ValueError(f"objective not found: {objective_id}")
            current = obj.get("review_status")
            if current is not None and status not in model.allowed_transitions(OBJECTIVE, current):
                raise ValueError(f"cannot move review status from {current} to {status}")

            cur.execute(
                "UPDATE objective SET review_status = %s, updated_at = now() WHERE id = %s RETURNING *",
                (status, uuid.UUID(objective_id)),
            )
            if status == "off_track":
                org_id = organization_id or _resolve_org(conn2, obj.get("location_id"))
                if org_id:
                    from services.management import workbench
                    item = workbench.create_work_item(
                        conn2, org_id, f"Corrective action for objective {objective_id}",
                        created_by_type=reviewer_type, created_by_id=reviewer_id,
                        objective_id=objective_id, priority="high",
                    )
                    corrective_work_item_id = str(item["id"])

            cur.execute(
                """
                INSERT INTO objective_review (
                    objective_id, reviewer_type, reviewer_id, status, notes, corrective_work_item_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    uuid.UUID(objective_id), reviewer_type,
                    uuid.UUID(reviewer_id) if reviewer_id else None, status, notes,
                    uuid.UUID(corrective_work_item_id) if corrective_work_item_id else None,
                ),
            )
            review = cur.fetchone()
            conn2.commit()
            return review, corrective_work_item_id
    finally:
        if own:
            conn2.close()


def list_reviews(conn, objective_id: str) -> Sequence[Mapping]:
    return model._rows(
        conn, "SELECT * FROM objective_review WHERE objective_id = %s ORDER BY review_date DESC",
        (uuid.UUID(objective_id),),
    )


def objective_health(conn, objective_id: str) -> Optional[str]:
    row = model._row(conn, "SELECT review_status FROM objective WHERE id = %s", (uuid.UUID(objective_id),))
    return row["review_status"] if row else None


def _resolve_org(conn, location_id):
    if not location_id:
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_id FROM organization_member WHERE location_id = %s LIMIT 1",
            (uuid.UUID(str(location_id)),),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None
