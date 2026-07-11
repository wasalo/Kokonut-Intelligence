"""Project Credit Class Enrollment: apply → approve/reject/terminate workflow."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.enrollment")

VALID_ENROLLMENT_STATUSES = {"applied", "changes_requested", "accepted", "rejected", "terminated"}

VALID_STATUS_TRANSITIONS = {
    "applied": ["changes_requested", "accepted", "rejected"],
    "changes_requested": ["changes_requested", "accepted", "rejected"],
    "accepted": ["terminated"],
    "rejected": [],
    "terminated": [],
}


def apply_to_class(
    conn,
    location_id: str,
    credit_class_id: str,
    application_metadata: str = None,
    applied_by: str = None,
) -> dict:
    existing = conn.execute(
        conn.text(
            "SELECT id, status FROM project_credit_class_enrollment "
            "WHERE location_id = :lid AND credit_class_id = :ccid"
        ),
        {"lid": location_id, "ccid": credit_class_id},
    ).mappings().first()

    if existing and existing["status"] in ("applied", "changes_requested"):
        raise ValueError(f"Application already exists with status: {existing['status']}")
    if existing and existing["status"] == "accepted":
        raise ValueError("Project is already enrolled in this credit class")

    if existing:
        conn.execute(
            conn.text(
                "UPDATE project_credit_class_enrollment SET "
                "status = 'applied', application_metadata = :am, "
                "applied_by = :ab, applied_at = NOW(), "
                "evaluated_by = NULL, evaluated_at = NULL, enrollment_metadata = NULL "
                "WHERE id = :id"
            ),
            {"am": application_metadata, "ab": applied_by, "id": str(existing["id"])},
        )
        return {"id": str(existing["id"]), "status": "applied", "reapplied": True}

    result = conn.execute(
        conn.text(
            "INSERT INTO project_credit_class_enrollment "
            "(location_id, credit_class_id, application_metadata, applied_by) "
            "VALUES (:lid, :ccid, :am, :ab) RETURNING id"
        ),
        {"lid": location_id, "ccid": credit_class_id, "am": application_metadata, "ab": applied_by},
    ).mappings().first()

    logger.info("Project %s applied to credit class %s", location_id, credit_class_id)
    return {"id": str(result["id"]), "status": "applied"}


def evaluate_application(
    conn,
    enrollment_id: str,
    issuer_address: str,
    new_status: str,
    enrollment_metadata: str = None,
) -> dict:
    if new_status not in VALID_ENROLLMENT_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    enrollment = conn.execute(
        conn.text("SELECT * FROM project_credit_class_enrollment WHERE id = :eid"),
        {"eid": enrollment_id},
    ).mappings().first()

    if not enrollment:
        raise ValueError(f"Enrollment not found: {enrollment_id}")

    current_status = enrollment["status"]
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(f"Cannot transition from '{current_status}' to '{new_status}'. Allowed: {allowed}")

    conn.execute(
        conn.text(
            "UPDATE project_credit_class_enrollment SET "
            "status = :ns, enrollment_metadata = :em, "
            "evaluated_by = :eb, evaluated_at = NOW() "
            "WHERE id = :eid"
        ),
        {"ns": new_status, "em": enrollment_metadata, "eb": issuer_address, "eid": enrollment_id},
    )

    logger.info("Enrollment %s evaluated: %s → %s by %s", enrollment_id, current_status, new_status, issuer_address)
    return {"id": enrollment_id, "old_status": current_status, "new_status": new_status}


def get_enrollment(conn, location_id: str, credit_class_id: str) -> dict | None:
    result = conn.execute(
        conn.text(
            "SELECT * FROM project_credit_class_enrollment "
            "WHERE location_id = :lid AND credit_class_id = :ccid"
        ),
        {"lid": location_id, "ccid": credit_class_id},
    ).mappings().first()
    return dict(result) if result else None


def get_enrollment_by_id(conn, enrollment_id: str) -> dict | None:
    result = conn.execute(
        conn.text("SELECT * FROM project_credit_class_enrollment WHERE id = :eid"),
        {"eid": enrollment_id},
    ).mappings().first()
    return dict(result) if result else None


def list_enrollments_by_project(conn, location_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT e.*, cc.name AS class_name, cc.credit_type "
            "FROM project_credit_class_enrollment e "
            "JOIN credit_class cc ON cc.id = e.credit_class_id "
            "WHERE e.location_id = :lid ORDER BY e.applied_at DESC"
        ),
        {"lid": location_id},
    )
    return [dict(r) for r in result.mappings()]


def list_enrollments_by_class(conn, credit_class_id: str, status: str = None) -> list[dict]:
    conditions = ["e.credit_class_id = :ccid"]
    params: dict[str, Any] = {"ccid": credit_class_id}
    if status:
        conditions.append("e.status = :s")
        params["s"] = status
    where = " AND ".join(conditions)
    result = conn.execute(
        conn.text(
            f"SELECT e.*, l.name AS location_name "
            f"FROM project_credit_class_enrollment e "
            f"JOIN location l ON l.id = e.location_id "
            f"WHERE {where} ORDER BY e.applied_at DESC"
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


def terminate_enrollment(conn, enrollment_id: str, evaluated_by: str = None) -> dict:
    enrollment = get_enrollment_by_id(conn, enrollment_id)
    if not enrollment:
        raise ValueError(f"Enrollment not found: {enrollment_id}")
    if enrollment["status"] != "accepted":
        raise ValueError(f"Only accepted enrollments can be terminated, current: {enrollment['status']}")

    conn.execute(
        conn.text(
            "UPDATE project_credit_class_enrollment SET "
            "status = 'terminated', evaluated_by = :eb, evaluated_at = NOW() "
            "WHERE id = :eid"
        ),
        {"eb": evaluated_by, "eid": enrollment_id},
    )

    logger.info("Enrollment %s terminated", enrollment_id)
    return {"id": enrollment_id, "status": "terminated"}
