"""Curriculum analytics for structured training programs.

Tracks program completion, competency coverage, credential status,
and training ROI.

Usage:
    python3 -m services.analytics --curriculum-completion --enrollment-id UUID
    python3 -m services.analytics --competency-coverage --location-id UUID
    python3 -m services.analytics --training-roi --program-id UUID
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.curriculum")


def compute_curriculum_completion(conn, enrollment_id: str) -> Dict[str, Any]:
    """Compute progress through a training program."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get enrollment details
    cur.execute("""
        SELECT te.*, tp.program_name, tp.program_type
        FROM training_enrollment te
        JOIN training_program tp ON tp.id = te.program_id
        WHERE te.id = %s
    """, (enrollment_id,))
    enrollment = cur.fetchone()
    if not enrollment:
        cur.close()
        return {"status": "error", "message": "Enrollment not found"}

    enrollment = dict(enrollment)
    program_id = enrollment["program_id"]

    # Count total lessons in program
    cur.execute("""
        SELECT COUNT(*) AS total_lessons
        FROM training_lesson tl
        JOIN training_module tm ON tl.module_id = tm.id
        WHERE tm.program_id = %s
    """, (program_id,))
    total = dict(cur.fetchone() or {})
    total_lessons = int(total.get("total_lessons", 0) or 0)

    # Count completed lessons
    cur.execute("""
        SELECT COUNT(DISTINCT tp.lesson_id) AS completed_lessons
        FROM training_progress tp
        WHERE tp.enrollment_id = %s AND tp.lesson_id IS NOT NULL
    """, (enrollment_id,))
    completed = dict(cur.fetchone() or {})
    completed_lessons = int(completed.get("completed_lessons", 0) or 0)

    # Module progress
    cur.execute("""
        SELECT
            tm.id AS module_id,
            tm.module_name,
            tm.sequence_order,
            (SELECT COUNT(*) FROM training_lesson tl WHERE tl.module_id = tm.id) AS total_lessons,
            (SELECT COUNT(DISTINCT tp.lesson_id) FROM training_progress tp
             WHERE tp.enrollment_id = %s AND tp.module_id = tm.id) AS completed_lessons
        FROM training_module tm
        WHERE tm.program_id = %s
        ORDER BY tm.sequence_order
    """, (enrollment_id, program_id))
    modules = []
    for row in cur.fetchall():
        m = dict(row)
        total = m["total_lessons"]
        done = m["completed_lessons"]
        m["completion_pct"] = round(done / total * 100, 1) if total > 0 else 0
        m["status"] = "completed" if done == total and total > 0 else "in_progress" if done > 0 else "not_started"
        modules.append(m)

    # Average score
    cur.execute("""
        SELECT AVG(score) AS avg_score, COUNT(*) AS scored_lessons
        FROM training_progress
        WHERE enrollment_id = %s AND score IS NOT NULL
    """, (enrollment_id,))
    scores = dict(cur.fetchone() or {})

    cur.close()

    return {
        "enrollment_id": enrollment_id,
        "participant_name": enrollment["participant_name"],
        "program_name": enrollment["program_name"],
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "completion_pct": round(completed_lessons / total_lessons * 100, 1) if total_lessons > 0 else 0,
        "avg_score": round(float(scores.get("avg_score", 0) or 0), 1),
        "enrollment_status": enrollment["status"],
        "modules": modules,
    }


def compute_competency_coverage(conn, location_id: str) -> Dict[str, Any]:
    """Compute which competencies are met vs missing for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all competencies for programs the location is enrolled in
    cur.execute("""
        SELECT DISTINCT
            cf.id AS competency_id,
            cf.competency_name,
            cf.description,
            cf.passing_score,
            tm.module_name,
            tp.program_name
        FROM competency_framework cf
        JOIN training_module tm ON cf.module_id = tm.id
        JOIN training_program tp ON tm.program_id = tp.id
        JOIN training_enrollment te ON te.program_id = tp.id
        WHERE te.location_id = %s
        AND te.status IN ('enrolled', 'in_progress', 'completed')
        AND cf.status = 'active'
    """, (location_id,))
    competencies = [dict(r) for r in cur.fetchall()]

    # Check which competencies have been met
    met_competencies = []
    unmet_competencies = []

    for comp in competencies:
        cur.execute("""
            SELECT MAX(tp.score) AS best_score
            FROM training_progress tp
            JOIN training_enrollment te ON tp.enrollment_id = te.id
            WHERE te.location_id = %s
            AND tp.module_id = (SELECT module_id FROM competency_framework WHERE id = %s)
        """, (location_id, comp["competency_id"]))
        row = cur.fetchone()
        best_score = float(row["best_score"]) if row and row["best_score"] else 0

        comp["best_score"] = best_score
        comp["met"] = best_score >= float(comp["passing_score"])

        if comp["met"]:
            met_competencies.append(comp)
        else:
            unmet_competencies.append(comp)

    cur.close()

    total = len(competencies)
    met = len(met_competencies)

    return {
        "location_id": location_id,
        "total_competencies": total,
        "met_competencies": met,
        "coverage_pct": round(met / total * 100, 1) if total > 0 else 0,
        "met": [{"name": c["competency_name"], "score": c["best_score"], "module": c["module_name"]} for c in met_competencies],
        "unmet": [{"name": c["competency_name"], "score": c["best_score"], "passing": c["passing_score"], "module": c["module_name"]} for c in unmet_competencies],
    }


def compute_training_roi(conn, program_id: str) -> Dict[str, Any]:
    """Compute training ROI: cost per competency earned, improvement per module."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Program details
    cur.execute("SELECT * FROM training_program WHERE id = %s", (program_id,))
    program = cur.fetchone()
    if not program:
        cur.close()
        return {"status": "error", "message": "Program not found"}

    program = dict(program)

    # Enrollment stats
    cur.execute("""
        SELECT
            COUNT(*) AS total_enrolled,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
            AVG(EXTRACT(EPOCH FROM (actual_completion - enrollment_date)) / 86400) AS avg_completion_days
        FROM training_enrollment
        WHERE program_id = %s
    """, (program_id,))
    enrollment_stats = dict(cur.fetchone() or {})

    # Competency stats
    cur.execute("""
        SELECT COUNT(*) AS total_competencies
        FROM competency_framework
        WHERE module_id IN (SELECT id FROM training_module WHERE program_id = %s)
        AND status = 'active'
    """, (program_id,))
    comp_stats = dict(cur.fetchone() or {})

    # Credentials earned
    cur.execute("""
        SELECT COUNT(*) AS credentials_issued
        FROM credential
        WHERE program_id = %s AND status = 'issued'
    """, (program_id,))
    cred_stats = dict(cur.fetchone() or {})

    # Training cost from social impact valuation
    cur.execute("""
        SELECT COALESCE(SUM(estimated_value_usd), 0) AS training_cost
        FROM social_impact_valuation
        WHERE impact_category = 'training'
        AND location_id IN (SELECT location_id FROM training_enrollment WHERE program_id = %s)
    """, (program_id,))
    cost_stats = dict(cur.fetchone() or {})

    cur.close()

    total_enrolled = int(enrollment_stats.get("total_enrolled", 0) or 0)
    completed = int(enrollment_stats.get("completed", 0) or 0)
    total_competencies = int(comp_stats.get("total_competencies", 0) or 0)
    credentials = int(cred_stats.get("credentials_issued", 0) or 0)
    training_cost = float(cost_stats.get("training_cost", 0) or 0)

    return {
        "program_id": program_id,
        "program_name": program["program_name"],
        "total_enrolled": total_enrolled,
        "completed": completed,
        "completion_rate_pct": round(completed / total_enrolled * 100, 1) if total_enrolled > 0 else 0,
        "avg_completion_days": round(float(enrollment_stats.get("avg_completion_days", 0) or 0), 1),
        "total_competencies": total_competencies,
        "credentials_issued": credentials,
        "training_cost": round(training_cost, 2),
        "cost_per_enrollment": round(training_cost / total_enrolled, 2) if total_enrolled > 0 else 0,
        "cost_per_competency": round(training_cost / total_competencies, 2) if total_competencies > 0 else 0,
        "cost_per_credential": round(training_cost / credentials, 2) if credentials > 0 else 0,
    }
