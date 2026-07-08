"""Grant network analytics: grant history, regional chapters, network diversity."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_grant_history_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize grant application history for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT application_status, grant_cycle,
               COUNT(*) AS application_count,
               SUM(amount_requested) AS total_requested,
               SUM(COALESCE(amount_awarded, 0)) AS total_awarded,
               SUM(CASE WHEN is_returning_applicant THEN 1 ELSE 0 END) AS returning_count
        FROM grant_application_history
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY application_status, grant_cycle
        ORDER BY grant_cycle DESC, application_status
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    applications = []
    for row in rows:
        applications.append({
            "application_status": row[0],
            "grant_cycle": row[1],
            "application_count": row[2],
            "total_requested": round(float(row[3] or 0), 2),
            "total_awarded": round(float(row[4] or 0), 2),
            "returning_count": row[5],
        })
    total_apps = sum(a["application_count"] for a in applications)
    funded = sum(a["application_count"] for a in applications if a["application_status"] == "funded")
    funding_rate = round(funded / total_apps * 100, 2) if total_apps > 0 else 0
    total_awarded = sum(a["total_awarded"] for a in applications)
    return {
        "location_id": location_id,
        "applications": applications,
        "total_applications": total_apps,
        "funded_applications": funded,
        "funding_rate_pct": funding_rate,
        "total_awarded": round(total_awarded, 2),
    }


def compute_network_diversity_summary(conn) -> dict[str, Any]:
    """Summarize network diversity across regional chapters."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rc.chapter_name, rc.geographic_region, rc.country,
               COUNT(DISTINCT nm.location_id) AS farm_count,
               COUNT(DISTINCT l.country) AS countries_represented
        FROM regional_chapter rc
        JOIN network_membership nm ON nm.chapter_id = rc.id AND nm.status = 'active'
        JOIN location l ON l.id = nm.location_id
        WHERE rc.status = 'active'
        GROUP BY rc.id, rc.chapter_name, rc.geographic_region, rc.country
        ORDER BY farm_count DESC
        """,
    )
    rows = cur.fetchall()
    cur.close()
    chapters = []
    for row in rows:
        chapters.append({
            "chapter_name": row[0],
            "geographic_region": row[1],
            "country": row[2],
            "farm_count": row[3],
            "countries_represented": row[4],
        })
    total_farms = sum(c["farm_count"] for c in chapters)
    unique_countries = len(set(c["country"] for c in chapters))
    return {
        "chapters": chapters,
        "total_chapters": len(chapters),
        "total_farms": total_farms,
        "unique_countries": unique_countries,
    }


def compute_regional_chapter_detail(conn, chapter_id: str) -> dict[str, Any]:
    """Get detailed information about a regional chapter."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rc.chapter_name, rc.description, rc.geographic_region,
               rc.country, rc.chapter_type, rc.founding_date,
               (SELECT COUNT(*) FROM network_membership nm WHERE nm.chapter_id = rc.id AND nm.status = 'active') AS member_count
        FROM regional_chapter rc
        WHERE rc.id = %s AND rc.status = 'active'
        """,
        (chapter_id,),
    )
    chapter = cur.fetchone()
    if not chapter:
        cur.close()
        return {"chapter_id": chapter_id, "error": "Chapter not found"}
    cur.execute(
        """
        SELECT nm.location_id, l.name AS location_name, l.country,
               nm.membership_type, nm.role, nm.join_date
        FROM network_membership nm
        JOIN location l ON l.id = nm.location_id
        WHERE nm.chapter_id = %s AND nm.status = 'active'
        ORDER BY nm.join_date
        """,
        (chapter_id,),
    )
    members = cur.fetchall()
    cur.close()
    member_list = []
    for row in members:
        member_list.append({
            "location_id": str(row[0]),
            "location_name": row[1],
            "country": row[2],
            "membership_type": row[3],
            "role": row[4],
            "join_date": str(row[5]) if row[5] else None,
        })
    return {
        "chapter_id": chapter_id,
        "chapter_name": chapter[0],
        "description": chapter[1],
        "geographic_region": chapter[2],
        "country": chapter[3],
        "chapter_type": chapter[4],
        "founding_date": str(chapter[5]) if chapter[5] else None,
        "member_count": chapter[6],
        "members": member_list,
    }
