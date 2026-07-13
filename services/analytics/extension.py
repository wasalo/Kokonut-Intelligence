#!/usr/bin/env python3
"""
Digital Extension Services

Farmer training modules, peer learning networks, content delivery,
skill assessment, and training effectiveness analytics.

Usage:
    python -m services.analytics.extension create-module --title "Soil Health 101" --category soil_health --content-type guide
    python -m services.analytics.extension list-modules --category soil_health --difficulty beginner
    python -m services.analytics.extension enroll --farmer-id FARMER --module-id UUID
    python -m services.analytics.extension update-progress --progress-id UUID --status completed --score 85
    python -m services.analytics.extension farmer-progress --farmer-id FARMER
    python -m services.analytics.extension module-stats --module-id UUID
    python -m services.analytics.extension create-peer-group --name "Adelphi FFS" --topic soil_health
    python -m services.analytics.extension add-peer-member --group-id UUID --farmer-id FARMER --role member
    python -m services.analytics.extension peer-groups --location-id UUID
    python -m services.analytics.extension deliver --farmer-id FARMER --module-id UUID --channel sms
    python -m services.analytics.extension delivery-stats --farmer-id FARMER
    python -m services.analytics.extension record-assessment --farmer-id FARMER --module-id UUID --type pre_test --score 60
    python -m services.analytics.extension effectiveness --location-id UUID
    python -m services.analytics.extension recommend --farmer-id FARMER --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.extension")


# ============================================================
# 1. Create Training Module
# ============================================================

def create_module(
    conn,
    title: str,
    category: str,
    content_type: str,
    content_url: str = None,
    duration_min: int = None,
    difficulty: str = "beginner",
    description: str = None,
    language: str = "en",
    tags: list = None,
    prerequisites: list = None,
    is_public: bool = True,
    metadata: dict = None,
) -> dict:
    """Create a new training module."""
    cur = conn.cursor()
    module_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO extension_module
                (id, module_name, description, category, difficulty, content_type,
                 content_url, duration_minutes, language, tags, prerequisites,
                 is_public, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s::jsonb)
            RETURNING id, created_at
            """,
            (
                module_id, title, description, category, difficulty, content_type,
                content_url, duration_min, language,
                tags or [], prerequisites or [], is_public,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Created extension module %s: %s", module_id[:8], title)
        return {
            "module_id": module_id,
            "title": title,
            "category": category,
            "content_type": content_type,
            "difficulty": difficulty,
            "status": "draft",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 2. List Modules
# ============================================================

def list_modules(
    conn,
    category: str = None,
    difficulty: str = None,
    content_type: str = None,
    status: str = "active",
) -> list[dict]:
    """List available training modules with optional filters."""
    cur = conn.cursor()

    try:
        where_clauses = []
        params = []

        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if category:
            where_clauses.append("category = %s")
            params.append(category)
        if difficulty:
            where_clauses.append("difficulty = %s")
            params.append(difficulty)
        if content_type:
            where_clauses.append("content_type = %s")
            params.append(content_type)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        cur.execute(
            f"""
            SELECT id, module_name, description, category, difficulty, content_type,
                   content_url, duration_minutes, language, tags, status, created_at
            FROM extension_module
            WHERE {where_sql}
            ORDER BY created_at DESC
            """,
            tuple(params),
        )
        cols = [d[0] for d in cur.description]
        modules = [dict(zip(cols, row)) for row in cur.fetchall()]

        for m in modules:
            m["id"] = str(m["id"])
            if m.get("created_at"):
                m["created_at"] = m["created_at"].isoformat()
            if m.get("tags") is None:
                m["tags"] = []

        return modules
    finally:
        cur.close()


# ============================================================
# 3. Enroll Farmer
# ============================================================

def enroll_farmer(
    conn,
    farmer_id: str,
    module_id: str,
    location_id: str = None,
    metadata: dict = None,
) -> dict:
    """Enroll a farmer in a training module."""
    cur = conn.cursor()
    progress_id = str(uuid.uuid4())

    try:
        if not location_id:
            cur.execute(
                "SELECT id FROM location LIMIT 1",
            )
            row = cur.fetchone()
            location_id = str(row[0]) if row else None

        if not location_id:
            raise ValueError("No location_id provided and no locations exist")

        cur.execute(
            """
            SELECT id FROM learning_progress
            WHERE module_id = %s AND farmer_name = %s AND location_id = %s
            """,
            (module_id, farmer_id, location_id),
        )
        if cur.fetchone():
            raise ValueError(f"Farmer {farmer_id} already enrolled in module {module_id}")

        cur.execute(
            """
            INSERT INTO learning_progress
                (id, location_id, module_id, farmer_name, progress_pct, status, metadata)
            VALUES (%s, %s, %s, %s, 0.00, 'in_progress', %s::jsonb)
            RETURNING id, started_at
            """,
            (progress_id, location_id, module_id, farmer_id, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Enrolled farmer %s in module %s", farmer_id[:16], module_id[:8])
        return {
            "progress_id": progress_id,
            "farmer_id": farmer_id,
            "module_id": module_id,
            "location_id": location_id,
            "status": "in_progress",
            "started_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 4. Update Progress
# ============================================================

def update_progress(
    conn,
    progress_id: str,
    status: str = None,
    score: float = None,
    progress_pct: float = None,
    time_spent_min: int = None,
    metadata: dict = None,
) -> dict:
    """Update learning progress for a module enrollment."""
    cur = conn.cursor()

    try:
        updates = ["updated_at = NOW()"]
        params = []

        if status is not None:
            updates.append("status = %s")
            params.append(status)
            if status == "completed":
                updates.append("completed_at = NOW()")
        if score is not None:
            updates.append("score = %s")
            params.append(score)
        if progress_pct is not None:
            updates.append("progress_pct = %s")
            params.append(progress_pct)
        if time_spent_min is not None:
            updates.append("time_spent_min = time_spent_min + %s")
            params.append(time_spent_min)
        if metadata is not None:
            updates.append("metadata = metadata || %s::jsonb")
            params.append(json.dumps(metadata))

        params.append(progress_id)

        cur.execute(
            f"""
            UPDATE learning_progress
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING id, module_id, farmer_name, progress_pct, score, status, completed_at
            """,
            tuple(params),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Progress record {progress_id} not found")

        conn.commit()

        logger.info("Updated progress %s → %s", progress_id[:8], row[5])
        return {
            "progress_id": str(row[0]),
            "module_id": str(row[1]),
            "farmer_id": row[2],
            "progress_pct": float(row[3]) if row[3] else 0,
            "score": float(row[4]) if row[4] else None,
            "status": row[5],
            "completed_at": row[6].isoformat() if row[6] else None,
        }
    finally:
        cur.close()


# ============================================================
# 5. Get Farmer Progress
# ============================================================

def get_farmer_progress(conn, farmer_id: str) -> dict:
    """Get all module progress for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT lp.id, lp.module_id, em.module_name, em.category, em.difficulty,
                   lp.progress_pct, lp.score, lp.time_spent_min, lp.attempts,
                   lp.started_at, lp.completed_at, lp.status
            FROM learning_progress lp
            JOIN extension_module em ON em.id = lp.module_id
            WHERE lp.farmer_name = %s
            ORDER BY lp.started_at DESC
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        for r in rows:
            r["id"] = str(r["id"])
            r["module_id"] = str(r["module_id"])
            if r.get("started_at"):
                r["started_at"] = r["started_at"].isoformat()
            if r.get("completed_at"):
                r["completed_at"] = r["completed_at"].isoformat()

        total = len(rows)
        completed = sum(1 for r in rows if r["status"] == "completed")
        in_progress = sum(1 for r in rows if r["status"] == "in_progress")
        avg_score = None
        scored = [r["score"] for r in rows if r.get("score") is not None]
        if scored:
            avg_score = round(sum(scored) / len(scored), 1)

        return {
            "farmer_id": farmer_id,
            "total_enrolled": total,
            "completed": completed,
            "in_progress": in_progress,
            "avg_score": avg_score,
            "modules": rows,
        }
    finally:
        cur.close()


# ============================================================
# 6. Module Stats
# ============================================================

def get_module_stats(conn, module_id: str) -> dict:
    """Get completion and performance stats for a module."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_enrolled,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                ROUND(AVG(score) FILTER (WHERE score IS NOT NULL), 1) AS avg_score,
                ROUND(AVG(time_spent_min) FILTER (WHERE time_spent_min > 0), 0) AS avg_time_min,
                ROUND(AVG(progress_pct), 1) AS avg_progress,
                MIN(started_at) AS first_enrolled,
                MAX(completed_at) AS last_completed
            FROM learning_progress
            WHERE module_id = %s
            """,
            (module_id,),
        )
        row = cur.fetchone()

        cur.execute(
            "SELECT module_name, category, difficulty FROM extension_module WHERE id = %s",
            (module_id,),
        )
        mod = cur.fetchone()

        stats = {
            "module_id": module_id,
            "module_name": mod[0] if mod else None,
            "category": mod[1] if mod else None,
            "difficulty": mod[2] if mod else None,
            "total_enrolled": int(row[0]) if row[0] else 0,
            "completed": int(row[1]) if row[1] else 0,
            "in_progress": int(row[2]) if row[2] else 0,
            "failed": int(row[3]) if row[3] else 0,
            "avg_score": float(row[4]) if row[4] else None,
            "avg_time_min": int(row[5]) if row[5] else None,
            "avg_progress_pct": float(row[6]) if row[6] else 0,
            "first_enrolled": row[7].isoformat() if row[7] else None,
            "last_completed": row[8].isoformat() if row[8] else None,
        }

        total = stats["total_enrolled"]
        stats["completion_rate_pct"] = round(stats["completed"] / total * 100, 1) if total > 0 else 0

        return stats
    finally:
        cur.close()


# ============================================================
# 7. Create Peer Group
# ============================================================

def create_peer_group(
    conn,
    name: str,
    topic: str,
    location_id: str = None,
    network_type: str = "learning_group",
    description: str = None,
    max_members: int = None,
    meeting_cadence: str = None,
    language: str = "en",
    metadata: dict = None,
) -> dict:
    """Create a peer learning group."""
    cur = conn.cursor()
    group_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO peer_network
                (id, network_name, description, network_type, location_id,
                 max_members, meeting_cadence, language, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
            RETURNING id, created_at
            """,
            (
                group_id, name, description, network_type, location_id,
                max_members, meeting_cadence, language,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Created peer group %s: %s", group_id[:8], name)
        return {
            "group_id": group_id,
            "name": name,
            "topic": topic,
            "network_type": network_type,
            "location_id": location_id,
            "status": "active",
            "created_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 8. Add Peer Member
# ============================================================

def add_peer_member(
    conn,
    group_id: str,
    farmer_id: str,
    role: str = "member",
    location_id: str = None,
    metadata: dict = None,
) -> dict:
    """Add a member to a peer learning group."""
    cur = conn.cursor()
    member_id = str(uuid.uuid4())

    try:
        if not location_id:
            cur.execute(
                "SELECT location_id FROM peer_network_member WHERE network_id = %s LIMIT 1",
                (group_id,),
            )
            row = cur.fetchone()
            if row:
                location_id = str(row[0])

        if not location_id:
            cur.execute(
                "SELECT location_id FROM peer_network WHERE id = %s",
                (group_id,),
            )
            row = cur.fetchone()
            location_id = str(row[0]) if row and row[0] else None

        if not location_id:
            raise ValueError("No location_id available for peer member")

        cur.execute(
            """
            SELECT id FROM peer_network_member
            WHERE network_id = %s AND farmer_name = %s AND status = 'active'
            """,
            (group_id, farmer_id),
        )
        if cur.fetchone():
            raise ValueError(f"Farmer {farmer_id} already a member of group {group_id}")

        cur.execute(
            """
            INSERT INTO peer_network_member
                (id, network_id, location_id, farmer_name, role, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, joined_at
            """,
            (member_id, group_id, location_id, farmer_id, role, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Added farmer %s to peer group %s", farmer_id[:16], group_id[:8])
        return {
            "member_id": member_id,
            "group_id": group_id,
            "farmer_id": farmer_id,
            "role": role,
            "joined_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 9. Get Peer Groups
# ============================================================

def get_peer_groups(conn, location_id: str = None) -> list[dict]:
    """List peer groups, optionally filtered by location."""
    cur = conn.cursor()

    try:
        if location_id:
            cur.execute(
                """
                SELECT pn.id, pn.network_name, pn.network_type, pn.location_id,
                       pn.max_members, pn.meeting_cadence, pn.status, pn.created_at,
                       COUNT(pnm.id) AS member_count
                FROM peer_network pn
                LEFT JOIN peer_network_member pnm ON pnm.network_id = pn.id AND pnm.status = 'active'
                WHERE pn.location_id = %s AND pn.status = 'active'
                GROUP BY pn.id
                ORDER BY pn.created_at DESC
                """,
                (location_id,),
            )
        else:
            cur.execute(
                """
                SELECT pn.id, pn.network_name, pn.network_type, pn.location_id,
                       pn.max_members, pn.meeting_cadence, pn.status, pn.created_at,
                       COUNT(pnm.id) AS member_count
                FROM peer_network pn
                LEFT JOIN peer_network_member pnm ON pnm.network_id = pn.id AND pnm.status = 'active'
                WHERE pn.status = 'active'
                GROUP BY pn.id
                ORDER BY pn.created_at DESC
                """,
            )

        cols = [d[0] for d in cur.description]
        groups = [dict(zip(cols, row)) for row in cur.fetchall()]

        for g in groups:
            g["id"] = str(g["id"])
            if g.get("location_id"):
                g["location_id"] = str(g["location_id"])
            if g.get("created_at"):
                g["created_at"] = g["created_at"].isoformat()
            g["member_count"] = int(g["member_count"])

        return groups
    finally:
        cur.close()


# ============================================================
# 10. Deliver Content
# ============================================================

def deliver_content(
    conn,
    farmer_id: str,
    module_id: str,
    channel: str,
    location_id: str = None,
    device_type: str = None,
    network_type: str = None,
    bandwidth_kbps: int = None,
    metadata: dict = None,
) -> dict:
    """Track content delivery to a farmer."""
    cur = conn.cursor()
    delivery_id = str(uuid.uuid4())

    try:
        if not location_id:
            cur.execute(
                "SELECT location_id FROM learning_progress WHERE module_id = %s AND farmer_name = %s LIMIT 1",
                (module_id, farmer_id),
            )
            row = cur.fetchone()
            location_id = str(row[0]) if row else None

        if not location_id:
            cur.execute("SELECT id FROM location LIMIT 1")
            row = cur.fetchone()
            location_id = str(row[0]) if row else None

        if not location_id:
            raise ValueError("No location_id available for content delivery")

        cur.execute(
            """
            INSERT INTO content_delivery
                (id, module_id, location_id, farmer_name, delivery_channel,
                 delivery_status, delivered_at, device_type, network_type,
                 bandwidth_kbps, metadata)
            VALUES (%s, %s, %s, %s, %s, 'sent', NOW(), %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                delivery_id, module_id, location_id, farmer_id, channel,
                device_type, network_type, bandwidth_kbps,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Delivered module %s to %s via %s", module_id[:8], farmer_id[:16], channel)
        return {
            "delivery_id": delivery_id,
            "farmer_id": farmer_id,
            "module_id": module_id,
            "channel": channel,
            "status": "sent",
            "delivered_at": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 11. Delivery Stats
# ============================================================

def get_delivery_stats(conn, farmer_id: str) -> dict:
    """Get content delivery statistics for a farmer."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                delivery_channel,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE delivery_status = 'delivered') AS delivered,
                COUNT(*) FILTER (WHERE delivery_status = 'viewed') AS viewed,
                COUNT(*) FILTER (WHERE delivery_status = 'clicked') AS clicked,
                COUNT(*) FILTER (WHERE delivery_status = 'failed') AS failed
            FROM content_delivery
            WHERE farmer_name = %s
            GROUP BY delivery_channel
            ORDER BY total DESC
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        by_channel = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT
                COUNT(*) AS total_deliveries,
                COUNT(*) FILTER (WHERE delivery_status IN ('delivered', 'viewed', 'clicked')) AS successful,
                COUNT(*) FILTER (WHERE delivery_status = 'failed') AS failed,
                COUNT(DISTINCT module_id) AS unique_modules
            FROM content_delivery
            WHERE farmer_name = %s
            """,
            (farmer_id,),
        )
        row = cur.fetchone()
        total = int(row[0]) if row[0] else 0

        return {
            "farmer_id": farmer_id,
            "total_deliveries": total,
            "successful": int(row[1]) if row[1] else 0,
            "failed": int(row[2]) if row[2] else 0,
            "unique_modules": int(row[3]) if row[3] else 0,
            "delivery_rate_pct": round(int(row[1]) / total * 100, 1) if total > 0 else 0,
            "by_channel": by_channel,
        }
    finally:
        cur.close()


# ============================================================
# 12. Record Assessment
# ============================================================

def record_assessment(
    conn,
    farmer_id: str,
    module_id: str,
    assessment_type: str,
    score: float,
    location_id: str = None,
    max_score: float = 100,
    questions_total: int = None,
    questions_correct: int = None,
    time_spent_min: int = None,
    assessor_name: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a skill assessment (pre-test, post-test, diagnostic, etc.)."""
    cur = conn.cursor()
    assessment_id = str(uuid.uuid4())

    try:
        if not location_id:
            cur.execute(
                "SELECT location_id FROM learning_progress WHERE module_id = %s AND farmer_name = %s LIMIT 1",
                (module_id, farmer_id),
            )
            row = cur.fetchone()
            location_id = str(row[0]) if row else None

        if not location_id:
            cur.execute("SELECT id FROM location LIMIT 1")
            row = cur.fetchone()
            location_id = str(row[0]) if row else None

        if not location_id:
            raise ValueError("No location_id available for assessment")

        cur.execute(
            """
            INSERT INTO skill_assessment
                (id, location_id, module_id, farmer_name, assessment_type,
                 score, max_score, questions_total, questions_correct,
                 time_spent_min, assessor_name, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, assessment_date
            """,
            (
                assessment_id, location_id, module_id, farmer_id, assessment_type,
                score, max_score, questions_total, questions_correct,
                time_spent_min, assessor_name, notes, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        logger.info("Recorded %s assessment for farmer %s: %.1f", assessment_type, farmer_id[:16], score)
        return {
            "assessment_id": assessment_id,
            "farmer_id": farmer_id,
            "module_id": module_id,
            "assessment_type": assessment_type,
            "score": score,
            "max_score": max_score,
            "assessment_date": row[1].isoformat() if row[1] else None,
        }
    finally:
        cur.close()


# ============================================================
# 13. Extension Effectiveness
# ============================================================

def get_extension_effectiveness(conn, location_id: str) -> dict:
    """Compute training effectiveness metrics for a location."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                em.category,
                em.module_name,
                COUNT(DISTINCT lp.id) AS enrollments,
                COUNT(DISTINCT CASE WHEN lp.status = 'completed' THEN lp.id END) AS completions,
                ROUND(AVG(CASE WHEN lp.status = 'completed' THEN lp.score END), 1) AS avg_score,
                ROUND(AVG(CASE WHEN lp.status = 'completed' THEN lp.time_spent_min END), 0) AS avg_time_min,
                (SELECT ROUND(AVG(sa.score), 1) FROM skill_assessment sa
                 WHERE sa.module_id = em.id AND sa.assessment_type = 'pre_test'
                   AND sa.location_id = %s) AS avg_pre_score,
                (SELECT ROUND(AVG(sa.score), 1) FROM skill_assessment sa
                 WHERE sa.module_id = em.id AND sa.assessment_type = 'post_test'
                   AND sa.location_id = %s) AS avg_post_score
            FROM extension_module em
            LEFT JOIN learning_progress lp ON lp.module_id = em.id AND lp.location_id = %s
            WHERE em.status = 'active'
            GROUP BY em.id, em.category, em.module_name
            HAVING COUNT(DISTINCT lp.id) > 0
            ORDER BY completions DESC
            """,
            (location_id, location_id, location_id),
        )
        cols = [d[0] for d in cur.description]
        modules = [dict(zip(cols, row)) for row in cur.fetchall()]

        for m in modules:
            e = m["enrollments"]
            c = m["completions"]
            m["completion_rate_pct"] = round(c / e * 100, 1) if e > 0 else 0
            if m["avg_pre_score"] and m["avg_post_score"]:
                m["skill_improvement"] = round(m["avg_post_score"] - m["avg_pre_score"], 1)
            else:
                m["skill_improvement"] = None

        total_enrollments = sum(m["enrollments"] for m in modules)
        total_completions = sum(m["completions"] for m in modules)
        overall_completion = round(total_completions / total_enrollments * 100, 1) if total_enrollments > 0 else 0

        scored = [m["avg_score"] for m in modules if m.get("avg_score") is not None]
        overall_avg_score = round(sum(scored) / len(scored), 1) if scored else None

        improved = [m for m in modules if m.get("skill_improvement") is not None]
        if improved:
            overall_improvement = round(sum(m["skill_improvement"] for m in improved) / len(improved), 1)
        else:
            overall_improvement = None

        categories = {}
        for m in modules:
            cat = m["category"]
            if cat not in categories:
                categories[cat] = {"enrollments": 0, "completions": 0}
            categories[cat]["enrollments"] += m["enrollments"]
            categories[cat]["completions"] += m["completions"]

        for cat in categories:
            e = categories[cat]["enrollments"]
            c = categories[cat]["completions"]
            categories[cat]["completion_rate_pct"] = round(c / e * 100, 1) if e > 0 else 0

        return {
            "location_id": location_id,
            "total_enrollments": total_enrollments,
            "total_completions": total_completions,
            "overall_completion_rate_pct": overall_completion,
            "overall_avg_score": overall_avg_score,
            "overall_skill_improvement": overall_improvement,
            "by_category": categories,
            "modules": modules,
        }
    finally:
        cur.close()


# ============================================================
# 14. Recommend Modules
# ============================================================

def recommend_modules(conn, farmer_id: str, location_id: str) -> dict:
    """Recommend training modules based on completion gaps and skill deficiencies."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT module_id, status, score
            FROM learning_progress
            WHERE farmer_name = %s AND location_id = %s
            """,
            (farmer_id, location_id),
        )
        cols = [d[0] for d in cur.description]
        enrolled = [dict(zip(cols, r)) for r in cur.fetchall()]

        enrolled_ids = set(str(r["module_id"]) for r in enrolled)
        completed_ids = set(str(r["module_id"]) for r in enrolled if r["status"] == "completed")
        in_progress = [r for r in enrolled if r["status"] == "in_progress"]

        low_scores = [
            str(r["module_id"]) for r in enrolled
            if r.get("score") is not None and float(r["score"]) < 60
        ]

        cur.execute(
            """
            SELECT sa.module_id, sa.score
            FROM skill_assessment sa
            WHERE sa.farmer_name = %s AND sa.location_id = %s
              AND sa.assessment_type = 'post_test'
            ORDER BY sa.assessment_date DESC
            """,
            (farmer_id, location_id),
        )
        recent_assessments = {str(row[0]): float(row[1]) for row in cur.fetchall()}

        weak_modules = [
            mid for mid, score in recent_assessments.items() if score < 60
        ]

        cur.execute(
            """
            SELECT id, module_name, category, difficulty, prerequisites
            FROM extension_module
            WHERE status = 'active'
            """,
        )
        all_modules = {}
        for row in cur.fetchall():
            all_modules[str(row[0])] = {
                "id": str(row[0]),
                "name": row[1],
                "category": row[2],
                "difficulty": row[3],
                "prerequisites": row[4] if row[4] else [],
            }

        recommendations = []

        for mid, mod in all_modules.items():
            if mid in completed_ids:
                continue

            reasons = []
            priority = 5

            prereqs = mod.get("prerequisites", []) or []
            unmet_prereqs = [p for p in prereqs if str(p) not in completed_ids]
            if unmet_prereqs:
                continue

            if mid in low_scores or mid in weak_modules:
                reasons.append("low_score")
                priority = 8

            if mid in enrolled_ids:
                reasons.append("in_progress")
                priority = max(priority, 7)
            else:
                reasons.append("not_started")

            if mod["difficulty"] == "beginner":
                priority = max(priority, 6)

            if not reasons:
                continue

            recommendations.append({
                "module_id": mid,
                "module_name": mod["name"],
                "category": mod["category"],
                "difficulty": mod["difficulty"],
                "priority": priority,
                "reasons": reasons,
            })

        recommendations.sort(key=lambda x: (-x["priority"], x["difficulty"]))

        return {
            "farmer_id": farmer_id,
            "location_id": location_id,
            "modules_completed": len(completed_ids),
            "modules_in_progress": len(in_progress),
            "modules_available": len(all_modules),
            "weak_areas": weak_modules,
            "recommendations": recommendations[:10],
        }
    finally:
        cur.close()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Digital extension services")
    sub = parser.add_subparsers(dest="command")

    # create-module
    cm = sub.add_parser("create-module", help="Create training module")
    cm.add_argument("--title", required=True)
    cm.add_argument("--category", required=True)
    cm.add_argument("--content-type", required=True, dest="content_type")
    cm.add_argument("--content-url", dest="content_url")
    cm.add_argument("--duration", type=int, dest="duration_min")
    cm.add_argument("--difficulty", default="beginner")
    cm.add_argument("--description")
    cm.add_argument("--language", default="en")
    cm.add_argument("--tags", nargs="*")
    cm.add_argument("--prerequisites", nargs="*")
    cm.add_argument("--json", action="store_true")

    # list-modules
    lm = sub.add_parser("list-modules", help="List training modules")
    lm.add_argument("--category")
    lm.add_argument("--difficulty")
    lm.add_argument("--content-type", dest="content_type")
    lm.add_argument("--status", default="active")
    lm.add_argument("--json", action="store_true")

    # enroll
    en = sub.add_parser("enroll", help="Enroll farmer in module")
    en.add_argument("--farmer-id", required=True)
    en.add_argument("--module-id", required=True)
    en.add_argument("--location-id")
    en.add_argument("--json", action="store_true")

    # update-progress
    up = sub.add_parser("update-progress", help="Update learning progress")
    up.add_argument("--progress-id", required=True)
    up.add_argument("--status")
    up.add_argument("--score", type=float)
    up.add_argument("--progress-pct", type=float)
    up.add_argument("--time-spent", type=int, dest="time_spent_min")
    up.add_argument("--json", action="store_true")

    # farmer-progress
    fp = sub.add_parser("farmer-progress", help="Get farmer progress")
    fp.add_argument("--farmer-id", required=True)
    fp.add_argument("--json", action="store_true")

    # module-stats
    ms = sub.add_parser("module-stats", help="Module completion stats")
    ms.add_argument("--module-id", required=True)
    ms.add_argument("--json", action="store_true")

    # create-peer-group
    cpg = sub.add_parser("create-peer-group", help="Create peer learning group")
    cpg.add_argument("--name", required=True)
    cpg.add_argument("--topic", required=True)
    cpg.add_argument("--location-id")
    cpg.add_argument("--network-type", default="learning_group")
    cpg.add_argument("--description")
    cpg.add_argument("--max-members", type=int)
    cpg.add_argument("--meeting-cadence")
    cpg.add_argument("--json", action="store_true")

    # add-peer-member
    apm = sub.add_parser("add-peer-member", help="Add member to peer group")
    apm.add_argument("--group-id", required=True)
    apm.add_argument("--farmer-id", required=True)
    apm.add_argument("--role", default="member")
    apm.add_argument("--json", action="store_true")

    # peer-groups
    pg = sub.add_parser("peer-groups", help="List peer groups")
    pg.add_argument("--location-id")
    pg.add_argument("--json", action="store_true")

    # deliver
    dl = sub.add_parser("deliver", help="Track content delivery")
    dl.add_argument("--farmer-id", required=True)
    dl.add_argument("--module-id", required=True)
    dl.add_argument("--channel", required=True)
    dl.add_argument("--location-id")
    dl.add_argument("--device-type")
    dl.add_argument("--network-type")
    dl.add_argument("--bandwidth", type=int, dest="bandwidth_kbps")
    dl.add_argument("--json", action="store_true")

    # delivery-stats
    ds = sub.add_parser("delivery-stats", help="Content delivery stats")
    ds.add_argument("--farmer-id", required=True)
    ds.add_argument("--json", action="store_true")

    # record-assessment
    ra = sub.add_parser("record-assessment", help="Record skill assessment")
    ra.add_argument("--farmer-id", required=True)
    ra.add_argument("--module-id", required=True)
    ra.add_argument("--type", required=True, dest="assessment_type")
    ra.add_argument("--score", type=float, required=True)
    ra.add_argument("--max-score", type=float, default=100)
    ra.add_argument("--questions-total", type=int)
    ra.add_argument("--questions-correct", type=int)
    ra.add_argument("--time-spent", type=int, dest="time_spent_min")
    ra.add_argument("--assessor")
    ra.add_argument("--notes")
    ra.add_argument("--json", action="store_true")

    # effectiveness
    ef = sub.add_parser("effectiveness", help="Training effectiveness")
    ef.add_argument("--location-id", required=True)
    ef.add_argument("--json", action="store_true")

    # recommend
    rc = sub.add_parser("recommend", help="Recommend modules")
    rc.add_argument("--farmer-id", required=True)
    rc.add_argument("--location-id", required=True)
    rc.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from ..ingestion.base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "create-module":
            result = create_module(
                db, args.title, args.category, args.content_type,
                content_url=args.content_url, duration_min=args.duration_min,
                difficulty=args.difficulty, description=args.description,
                language=args.language, tags=args.tags,
                prerequisites=args.prerequisites,
            )
        elif args.command == "list-modules":
            result = list_modules(
                db, category=args.category, difficulty=args.difficulty,
                content_type=args.content_type, status=args.status,
            )
        elif args.command == "enroll":
            result = enroll_farmer(
                db, args.farmer_id, args.module_id, location_id=args.location_id,
            )
        elif args.command == "update-progress":
            result = update_progress(
                db, args.progress_id, status=args.status, score=args.score,
                progress_pct=args.progress_pct, time_spent_min=args.time_spent_min,
            )
        elif args.command == "farmer-progress":
            result = get_farmer_progress(db, args.farmer_id)
        elif args.command == "module-stats":
            result = get_module_stats(db, args.module_id)
        elif args.command == "create-peer-group":
            result = create_peer_group(
                db, args.name, args.topic, location_id=args.location_id,
                network_type=args.network_type, description=args.description,
                max_members=args.max_members, meeting_cadence=args.meeting_cadence,
            )
        elif args.command == "add-peer-member":
            result = add_peer_member(
                db, args.group_id, args.farmer_id, role=args.role,
            )
        elif args.command == "peer-groups":
            result = get_peer_groups(db, location_id=args.location_id)
        elif args.command == "deliver":
            result = deliver_content(
                db, args.farmer_id, args.module_id, args.channel,
                location_id=args.location_id, device_type=args.device_type,
                network_type=args.network_type, bandwidth_kbps=args.bandwidth_kbps,
            )
        elif args.command == "delivery-stats":
            result = get_delivery_stats(db, args.farmer_id)
        elif args.command == "record-assessment":
            result = record_assessment(
                db, args.farmer_id, args.module_id, args.assessment_type,
                args.score, max_score=args.max_score,
                questions_total=args.questions_total,
                questions_correct=args.questions_correct,
                time_spent_min=args.time_spent_min,
                assessor_name=args.assessor, notes=args.notes,
            )
        elif args.command == "effectiveness":
            result = get_extension_effectiveness(db, args.location_id)
        elif args.command == "recommend":
            result = recommend_modules(db, args.farmer_id, args.location_id)

        print(json.dumps(result, indent=2, default=str))

    finally:
        db.close()


if __name__ == "__main__":
    main()
