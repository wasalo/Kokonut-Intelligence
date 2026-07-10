"""Content/sensemaking layer — content creation, publishing, and credibility."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.content")


def generate_narrative(
    conn,
    location_id: str,
    narrative_type: str = "combined",
    author_id: str = None,
) -> str:
    """Generate an AI-powered narrative from governed data.

    This is a template-based narrative generator that aggregates
    governed data into structured text. In production, this would
    integrate with an LLM for contextual interpretation.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Gather governed data
    data = {}

    # Farm info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    loc = cur.fetchone()
    location_name = loc["name"] if loc else "Unknown"

    # Carbon balance
    cur.execute("""
        SELECT total_sequestration_tonnes_co2e, total_emissions_tonnes_co2e, net_position
        FROM v_carbon_balance WHERE location_id = %s LIMIT 1
    """, (location_id,))
    carbon = dict(cur.fetchone() or {})

    # Training impact
    cur.execute("""
        SELECT COUNT(*) AS sessions, COALESCE(AVG(improvement_pct), 0) AS avg_improvement
        FROM training_session WHERE location_id = %s
    """, (location_id,))
    training = dict(cur.fetchone() or {})

    # Revenue
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM revenue_event WHERE location_id = %s
    """, (location_id,))
    revenue = dict(cur.fetchone() or {})

    # Externality
    cur.execute("""
        SELECT COALESCE(SUM(estimated_value_usd), 0) AS total_hidden_cost
        FROM hidden_cost_observation WHERE location_id = %s
    """, (location_id,))
    ext = dict(cur.fetchone() or {})

    cur.close()

    # Build narrative
    sequestration = float(carbon.get("total_sequestration_tonnes_co2e", 0) or 0)
    emissions = float(carbon.get("total_emissions_tonnes_co2e", 0) or 0)
    net = float(carbon.get("net_position", 0) or 0)
    rev = float(revenue.get("total_revenue", 0) or 0)
    hidden = float(ext.get("total_hidden_cost", 0) or 0)
    sessions = int(training.get("sessions", 0) or 0)
    improvement = float(training.get("avg_improvement", 0) or 0)

    narrative = f"## {location_name} — Impact Summary\n\n"
    narrative += f"**Carbon Position:** {net:+.1f} tonnes CO2e "
    narrative += f"(sequestered {sequestration:.1f}, emitted {emissions:.1f})\n\n"
    narrative += f"**Financial:** ${rev:,.0f} total revenue\n\n"
    narrative += f"**Capacity Building:** {sessions} training sessions with {improvement:.0f}% average improvement\n\n"
    narrative += f"**True Cost:** ${hidden:,.0f} in hidden externalities tracked\n\n"

    if net > 0:
        narrative += "**Assessment:** Net positive climate impact. The farm is sequestering more carbon than it emits."
    elif net == 0:
        narrative += "**Assessment:** Carbon neutral. Emissions and sequestration are balanced."
    else:
        narrative += "**Assessment:** Net emissions exceed sequestration. Mitigation measures recommended."

    # Create content piece
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO content_piece
            (location_id, author_id, content_type, title, body, summary, audience, status)
        VALUES (%s, %s, 'narrative', %s, %s, %s, 'public', 'draft')
        RETURNING id
    """, (
        location_id, author_id,
        f"{location_name} — {narrative_type.title()} Summary",
        narrative,
        f"Carbon net position: {net:+.1f}t CO2e, Revenue: ${rev:,.0f}",
    ))
    content_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    return content_id


def publish_content(
    conn,
    content_id: str,
    channels: List[str],
    audience_segment: str = "public",
) -> Dict[str, Any]:
    """Publish content to distribution channels."""
    cur = conn.cursor()

    # Update content status
    cur.execute("""
        UPDATE content_piece SET status = 'published', published_at = NOW()
        WHERE id = %s
    """, (content_id,))

    # Log distribution
    for channel in channels:
        cur.execute("""
            INSERT INTO content_distribution (content_id, channel, audience_segment)
            VALUES (%s, %s, %s)
        """, (content_id, channel, audience_segment))

    conn.commit()
    cur.close()

    return {"content_id": content_id, "channels": channels, "status": "published"}


def compute_sensemaking_score(conn, content_id: str) -> Dict[str, Any]:
    """Compute credibility score for content based on evidence and validation."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM content_piece WHERE id = %s", (content_id,))
    content = cur.fetchone()
    if not content:
        cur.close()
        return {"status": "error", "message": "Content not found"}

    content = dict(content)
    evidence_count = len(content.get("evidence_ids") or [])
    source_count = len(content.get("source_references") or [])

    # Evidence diversity score (0-100)
    evidence_diversity = min(100, evidence_count * 20)

    # Source credibility (0-100)
    source_credibility = min(100, source_count * 25)

    # Validation count
    cur.execute("""
        SELECT COUNT(*) AS validations FROM validator_review vr
        JOIN impact_estimate_post eep ON eep.id = vr.round_id
        WHERE eep.project_hash = %s
    """, (content.get("project_hash", ""),))
    val = dict(cur.fetchone() or {})
    validations = int(val.get("validations", 0) or 0)

    composite = (evidence_diversity * 0.4) + (source_credibility * 0.3) + (min(100, validations * 10) * 0.3)

    cur.execute("""
        INSERT INTO sensemaking_score
            (content_id, evidence_diversity_score, source_credibility_score,
             validation_count, composite_score)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (content_id, evidence_diversity, source_credibility, validations, round(composite, 2)))
    score_id = str(cur.fetchone()[0])

    # Update content piece
    cur.execute("UPDATE content_piece SET sensemaking_score = %s WHERE id = %s", (round(composite, 2), content_id))

    conn.commit()
    cur.close()

    return {
        "content_id": content_id,
        "sensemaking_score": round(composite, 2),
        "evidence_diversity": round(evidence_diversity, 2),
        "source_credibility": round(source_credibility, 2),
        "validations": validations,
    }
