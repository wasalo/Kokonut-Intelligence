"""Impact Value Chain analytics: task completion, weekly plan adherence, phase progress, framework steps."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_task_completion_rate(conn, location_id: str) -> dict[str, Any]:
    """Compute task completion rate and on-time delivery metrics."""
    cur = conn.cursor()

    # Overall task stats
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_tasks,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_tasks,
            COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_tasks,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_tasks,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_tasks,
            COUNT(*) FILTER (WHERE status = 'completed' AND end_date >= CURRENT_DATE) AS on_time_tasks,
            COUNT(*) FILTER (WHERE status = 'completed' AND end_date < CURRENT_DATE) AS late_tasks,
            COUNT(*) FILTER (WHERE priority = 'critical') AS critical_tasks,
            COUNT(*) FILTER (WHERE priority = 'critical' AND status = 'completed') AS critical_completed
        FROM farm_task
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()

    total = row[0] or 0
    completed = row[1] or 0
    in_progress = row[2] or 0
    pending = row[3] or 0
    cancelled = row[4] or 0
    on_time = row[5] or 0
    late = row[6] or 0
    critical = row[7] or 0
    critical_completed = row[8] or 0

    completion_pct = (completed / total * 100) if total > 0 else 0
    on_time_pct = (on_time / completed * 100) if completed > 0 else 0
    critical_completion_pct = (critical_completed / critical * 100) if critical > 0 else 0

    # By category
    cur.execute(
        """
        SELECT category,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'completed') AS completed,
               COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
               COUNT(*) FILTER (WHERE status = 'pending') AS pending
        FROM farm_task
        WHERE location_id = %s
        GROUP BY category
        ORDER BY total DESC
        """,
        (location_id,),
    )
    categories = [
        {
            "category": r[0],
            "total": r[1],
            "completed": r[2],
            "in_progress": r[3],
            "pending": r[4],
            "completion_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
        }
        for r in cur.fetchall()
    ]

    # By assignee
    cur.execute(
        """
        SELECT s.name AS assignee_name,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE ft.status = 'completed') AS completed
        FROM farm_task ft
        LEFT JOIN staff s ON ft.assignee_id = s.id
        WHERE ft.location_id = %s AND ft.assignee_id IS NOT NULL
        GROUP BY s.name
        ORDER BY total DESC
        """,
        (location_id,),
    )
    assignees = [
        {
            "assignee": r[0] or "Unassigned",
            "total": r[1],
            "completed": r[2],
            "completion_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
        }
        for r in cur.fetchall()
    ]

    # Cost tracking
    cur.execute(
        """
        SELECT
            SUM(estimated_cost_usd) AS total_estimated,
            SUM(actual_cost_usd) AS total_actual,
            COUNT(*) FILTER (WHERE actual_cost_usd IS NOT NULL AND estimated_cost_usd IS NOT NULL
                             AND actual_cost_usd > estimated_cost_usd) AS over_budget_count
        FROM farm_task
        WHERE location_id = %s
        """,
        (location_id,),
    )
    cost_row = cur.fetchone()
    cur.close()

    total_estimated = float(cost_row[0]) if cost_row[0] else 0
    total_actual = float(cost_row[1]) if cost_row[1] else 0
    budget_adherence = (total_actual / total_estimated * 100) if total_estimated > 0 else None

    result = {
        "location_id": location_id,
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "pending_tasks": pending,
        "cancelled_tasks": cancelled,
        "completion_pct": round(completion_pct, 1),
        "on_time_pct": round(on_time_pct, 1),
        "late_tasks": late,
        "critical_tasks": critical,
        "critical_completion_pct": round(critical_completion_pct, 1),
        "total_estimated_cost_usd": round(total_estimated, 2),
        "total_actual_cost_usd": round(total_actual, 2),
        "budget_adherence_pct": round(budget_adherence, 1) if budget_adherence else None,
        "categories": categories,
        "assignees": assignees,
    }

    logger.info("Task completion for %s: %d/%d (%.1f%%), on-time %.1f%%",
                location_id, completed, total, completion_pct, on_time_pct)
    return result


def compute_weekly_plan_adherence(conn, location_id: str) -> dict[str, Any]:
    """Compute weekly plan adherence metrics."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, plan_name, week_start, week_end,
               budget_forecast_usd, budget_actual_usd, status
        FROM weekly_plan
        WHERE location_id = %s
        ORDER BY week_start DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    plans = []
    for row in rows:
        forecast = float(row[4]) if row[4] else 0
        actual = float(row[5]) if row[5] else None
        adherence = (actual / forecast * 100) if forecast > 0 and actual is not None else None

        plans.append({
            "plan_id": str(row[0]),
            "plan_name": row[1],
            "week_start": str(row[2]) if row[2] else None,
            "week_end": str(row[3]) if row[3] else None,
            "budget_forecast_usd": round(forecast, 2),
            "budget_actual_usd": round(actual, 2) if actual is not None else None,
            "budget_adherence_pct": round(adherence, 1) if adherence else None,
            "status": row[6],
        })

    total_forecast = sum(p["budget_forecast_usd"] for p in plans)
    total_actual = sum(p["budget_actual_usd"] for p in plans if p["budget_actual_usd"] is not None)
    overall_adherence = (total_actual / total_forecast * 100) if total_forecast > 0 else None

    result = {
        "location_id": location_id,
        "total_plans": len(plans),
        "completed_plans": sum(1 for p in plans if p["status"] == "completed"),
        "active_plans": sum(1 for p in plans if p["status"] == "active"),
        "total_budget_forecast": round(total_forecast, 2),
        "total_budget_actual": round(total_actual, 2),
        "overall_adherence_pct": round(overall_adherence, 1) if overall_adherence else None,
        "plans": plans,
    }

    logger.info("Weekly plan adherence for %s: %.1f%%", location_id, overall_adherence or 0)
    return result


def compute_development_phase_progress(conn, location_id: str) -> dict[str, Any]:
    """Compute development phase progress."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, phase_name, description, phase_order,
               start_date, end_date, status
        FROM development_phase
        WHERE location_id = %s
        ORDER BY phase_order
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    phases = []
    for row in rows:
        from datetime import date, datetime as dt
        start = row[4]
        end = row[5]
        status = row[6]

        # Convert string dates to date objects if needed
        if isinstance(start, str):
            try:
                start = date.fromisoformat(start)
            except (ValueError, TypeError):
                start = None
        if isinstance(end, str):
            try:
                end = date.fromisoformat(end)
            except (ValueError, TypeError):
                end = None

        if status == "completed":
            progress = 100.0
        elif status == "pending":
            progress = 0.0
        elif start and end and status == "active":
            today = date.today()
            if today >= start and today <= end:
                progress = round((today - start).days / (end - start).days * 100, 1)
            elif today > end:
                progress = 100.0
            else:
                progress = 0.0
        else:
            progress = None

        phases.append({
            "phase_id": str(row[0]),
            "phase_name": row[1],
            "description": row[2],
            "phase_order": row[3],
            "start_date": str(row[4]) if row[4] else None,
            "end_date": str(row[5]) if row[5] else None,
            "status": row[6],
            "progress_pct": progress,
        })

    # Find current phase
    current = next((p for p in phases if p["status"] == "active"), None)
    completed_count = sum(1 for p in phases if p["status"] == "completed")

    result = {
        "location_id": location_id,
        "total_phases": len(phases),
        "completed_phases": completed_count,
        "current_phase": current["phase_name"] if current else None,
        "current_phase_progress": current["progress_pct"] if current else None,
        "overall_progress_pct": round(completed_count / len(phases) * 100, 1) if phases else 0,
        "phases": phases,
    }

    logger.info("Development phase progress for %s: %d/%d completed, current: %s",
                location_id, completed_count, len(phases), current["phase_name"] if current else "none")
    return result


def compute_framework_step_progress(conn, location_id: str) -> dict[str, Any]:
    """Compute framework step progress with prerequisite validation."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, step_name, description, step_order, step_type,
               duration_days, prerequisites, status
        FROM framework_step
        WHERE location_id = %s
        ORDER BY step_order
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    steps = []
    for row in rows:
        steps.append({
            "step_id": str(row[0]),
            "step_name": row[1],
            "description": row[2],
            "step_order": row[3],
            "step_type": row[4],
            "duration_days": row[5],
            "prerequisites": row[6] or [],
            "status": row[7],
        })

    completed_ids = {s["step_id"] for s in steps if s["status"] == "completed"}
    completed_count = sum(1 for s in steps if s["status"] == "completed")
    in_progress_count = sum(1 for s in steps if s["status"] == "in_progress")

    # Check prerequisite compliance
    for step in steps:
        prereqs = step.get("prerequisites", [])
        if prereqs and isinstance(prereqs, list):
            met = all(str(p) in completed_ids for p in prereqs)
            step["prerequisites_met"] = met
            step["blocked"] = not met and step["status"] == "pending"
        else:
            step["prerequisites_met"] = True
            step["blocked"] = False

    blocked_steps = [s for s in steps if s.get("blocked")]

    result = {
        "location_id": location_id,
        "total_steps": len(steps),
        "completed_steps": completed_count,
        "in_progress_steps": in_progress_count,
        "pending_steps": sum(1 for s in steps if s["status"] == "pending"),
        "blocked_steps": len(blocked_steps),
        "completion_pct": round(completed_count / len(steps) * 100, 1) if steps else 0,
        "steps": steps,
    }

    logger.info("Framework steps for %s: %d/%d completed, %d blocked",
                location_id, completed_count, len(steps), len(blocked_steps))
    return result
