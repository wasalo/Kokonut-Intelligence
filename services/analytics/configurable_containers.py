"""Configurable containers analytics: templates, specifications, needs, aspirations, objectives."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_farm_template_summary(conn, location_id: str = None) -> dict[str, Any]:
    """Summarize available farm templates."""
    cur = conn.cursor()
    if location_id:
        cur.execute(
            """
            SELECT ft.id, ft.template_name, ft.template_type, ft.version,
                   ft.default_zones, ft.default_governance_mechanism,
                   ft.default_impact_frameworks, ft.default_principles,
                   ft.suggested_farm_type, ft.tags,
                   COUNT(fs.id) AS instances_count
            FROM farm_template ft
            LEFT JOIN farm_specification fs ON fs.template_id = ft.id AND fs.status IN ('verified', 'published')
            WHERE ft.status IN ('verified', 'published')
            GROUP BY ft.id, ft.template_name, ft.template_type, ft.version,
                     ft.default_zones, ft.default_governance_mechanism,
                     ft.default_impact_frameworks, ft.default_principles,
                     ft.suggested_farm_type, ft.tags
            ORDER BY ft.template_name
            """,
        )
    else:
        cur.execute(
            """
            SELECT ft.id, ft.template_name, ft.template_type, ft.version,
                   ft.default_zones, ft.default_governance_mechanism,
                   ft.default_impact_frameworks, ft.default_principles,
                   ft.suggested_farm_type, ft.tags,
                   COUNT(fs.id) AS instances_count
            FROM farm_template ft
            LEFT JOIN farm_specification fs ON fs.template_id = ft.id AND fs.status IN ('verified', 'published')
            WHERE ft.status IN ('verified', 'published')
            GROUP BY ft.id, ft.template_name, ft.template_type, ft.version,
                     ft.default_zones, ft.default_governance_mechanism,
                     ft.default_impact_frameworks, ft.default_principles,
                     ft.suggested_farm_type, ft.tags
            ORDER BY ft.template_name
            """,
        )
    rows = cur.fetchall()
    cur.close()
    templates = []
    for row in rows:
        zones = row[4] if isinstance(row[4], list) else []
        templates.append({
            "template_id": str(row[0]),
            "template_name": row[1],
            "template_type": row[2],
            "version": row[3],
            "zone_count": len(zones),
            "default_governance": row[5],
            "default_frameworks": row[6],
            "default_principles": row[7],
            "suggested_farm_type": row[8],
            "tags": row[9],
            "instances_count": row[10],
        })
    return {
        "templates": templates,
        "total_templates": len(templates),
    }


def compute_farm_specification_status(conn, location_id: str) -> dict[str, Any]:
    """Summarize farm specification status for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT fs.id, fs.spec_name, fs.version, fs.is_override,
               fs.validation_status, fs.applied_at, fs.status,
               ft.template_name, ft.template_type,
               jsonb_array_length(fs.zones) AS zone_count
        FROM farm_specification fs
        LEFT JOIN farm_template ft ON ft.id = fs.template_id
        WHERE fs.location_id = %s
        ORDER BY fs.created_at DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    specs = []
    for row in rows:
        specs.append({
            "spec_id": str(row[0]),
            "spec_name": row[1],
            "version": row[2],
            "is_override": row[3],
            "validation_status": row[4],
            "applied_at": str(row[5]) if row[5] else None,
            "status": row[6],
            "template_name": row[7],
            "template_type": row[8],
            "zone_count": row[9],
        })
    return {
        "location_id": location_id,
        "specifications": specs,
        "total_specs": len(specs),
    }


def compute_needs_assessment_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize needs assessment for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT need_category, severity, urgency, mitigation_status,
               COUNT(*) AS need_count,
               AVG(CASE WHEN affected_count IS NOT NULL THEN affected_count END) AS avg_affected
        FROM needs_assessment
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY need_category, severity, urgency, mitigation_status
        ORDER BY
            CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END,
            need_count DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    needs = []
    for row in rows:
        needs.append({
            "need_category": row[0],
            "severity": row[1],
            "urgency": row[2],
            "mitigation_status": row[3],
            "need_count": row[4],
            "avg_affected_count": round(float(row[5] or 0), 1),
        })
    total = sum(n["need_count"] for n in needs)
    resolved = sum(n["need_count"] for n in needs if n["mitigation_status"] == "resolved")
    resolution_rate = round(resolved / total * 100, 2) if total > 0 else 0
    return {
        "location_id": location_id,
        "needs": needs,
        "total_needs": total,
        "resolved_needs": resolved,
        "resolution_rate_pct": resolution_rate,
    }


def compute_aspirations_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize stakeholder aspirations for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT aspiration_category, priority, status,
               COUNT(*) AS aspiration_count,
               AVG(timeline_months) AS avg_timeline_months
        FROM stakeholder_aspiration
        WHERE location_id = %s AND status IN ('approved', 'in_progress', 'achieved')
        GROUP BY aspiration_category, priority, status
        ORDER BY
            CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END,
            aspiration_count DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    aspirations = []
    for row in rows:
        aspirations.append({
            "aspiration_category": row[0],
            "priority": row[1],
            "status": row[2],
            "aspiration_count": row[3],
            "avg_timeline_months": round(float(row[4] or 0), 1),
        })
    total = sum(a["aspiration_count"] for a in aspirations)
    achieved = sum(a["aspiration_count"] for a in aspirations if a["status"] == "achieved")
    achievement_rate = round(achieved / total * 100, 2) if total > 0 else 0
    return {
        "location_id": location_id,
        "aspirations": aspirations,
        "total_aspirations": total,
        "achieved_aspirations": achieved,
        "achievement_rate_pct": achievement_rate,
    }


def compute_objectives_progress(conn, location_id: str) -> dict[str, Any]:
    """Summarize objectives progress for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.id, o.parent_id, o.objective_name, o.objective_type,
               o.category, o.target_value, o.current_value, o.unit,
               o.target_date, o.progress_pct, o.priority, o.status
        FROM objective o
        WHERE o.location_id = %s AND o.status IN ('approved', 'in_progress', 'achieved')
        ORDER BY o.target_date NULLS LAST, o.priority
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    objectives = []
    for row in rows:
        objectives.append({
            "objective_id": str(row[0]),
            "parent_id": str(row[1]) if row[1] else None,
            "objective_name": row[2],
            "objective_type": row[3],
            "category": row[4],
            "target_value": float(row[5]) if row[5] is not None else None,
            "current_value": float(row[6]) if row[6] is not None else None,
            "unit": row[7],
            "target_date": str(row[8]) if row[8] else None,
            "progress_pct": float(row[9]) if row[9] is not None else None,
            "priority": row[10],
            "status": row[11],
        })
    total = len(objectives)
    achieved = sum(1 for o in objectives if o["status"] == "achieved")
    in_progress = sum(1 for o in objectives if o["status"] == "in_progress")
    avg_progress = (
        sum(o["progress_pct"] or 0 for o in objectives if o["progress_pct"] is not None)
        / max(sum(1 for o in objectives if o["progress_pct"] is not None), 1)
    )
    return {
        "location_id": location_id,
        "objectives": objectives,
        "total_objectives": total,
        "achieved": achieved,
        "in_progress": in_progress,
        "avg_progress_pct": round(avg_progress, 2),
    }
