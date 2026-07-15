"""PESTEL Analysis service — macro-environment assessment per location."""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db
from services.common.logging import get_logger

logger = get_logger(__name__)

CATEGORIES = ("political", "economic", "social", "technological", "environmental", "legal")
FACTOR_TYPES = ("strength", "opportunity", "risk", "neutral")


def create_analysis(
    conn,
    location_id: str,
    title: str,
    period_start: str,
    period_end: str,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO pestel_analysis
               (location_id, title, period_start, period_end, created_by)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, location_id, title, period_start::text, period_end::text,
                         status, overall_score, factor_count, created_at""",
            (location_id, title, period_start, period_end, created_by),
        )
        row = dict(cur.fetchone())
        conn.commit()
        logger.info("Created PESTEL analysis %s for location %s", row["id"], location_id)
        return row


def add_factor(
    conn,
    analysis_id: str,
    category: str,
    factor_type: str,
    title: str,
    description: str = "",
    impact_score: float = 5.0,
    likelihood: float = 0.5,
    evidence_source: Optional[Dict] = None,
    location_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    if factor_type not in FACTOR_TYPES:
        raise ValueError(f"factor_type must be one of {FACTOR_TYPES}")

    if location_id is None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT location_id FROM pestel_analysis WHERE id = %s",
                (analysis_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Analysis {analysis_id} not found")
            location_id = str(row[0])

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO pestel_factor
               (analysis_id, location_id, category, factor_type, title, description,
                impact_score, likelihood, evidence_source, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, category, factor_type, title, impact_score, likelihood,
                         status, created_at""",
            (
                analysis_id, location_id, category, factor_type, title, description,
                impact_score, likelihood, json.dumps(evidence_source or {}),
                created_by,
            ),
        )
        factor = dict(cur.fetchone())

        cur.execute(
            """UPDATE pestel_analysis
               SET factor_count = (SELECT COUNT(*) FROM pestel_factor WHERE analysis_id = %s)
               WHERE id = %s""",
            (analysis_id, analysis_id),
        )
        conn.commit()
        logger.info("Added PESTEL factor %s (%s/%s)", factor["id"], category, factor_type)
        return factor


def list_analyses(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                """SELECT a.*, l.name AS location_name
                   FROM pestel_analysis a
                   LEFT JOIN location l ON l.id = a.location_id
                   WHERE a.location_id = %s
                   ORDER BY a.created_at DESC""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT a.*, l.name AS location_name
                   FROM pestel_analysis a
                   LEFT JOIN location l ON l.id = a.location_id
                   ORDER BY a.created_at DESC"""
            )
        return [dict(r) for r in cur.fetchall()]


def get_analysis(conn, analysis_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT a.*, l.name AS location_name
               FROM pestel_analysis a
               LEFT JOIN location l ON l.id = a.location_id
               WHERE a.id = %s""",
            (analysis_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        analysis = dict(row)

        cur.execute(
            """SELECT * FROM pestel_factor
               WHERE analysis_id = %s
               ORDER BY category, factor_type""",
            (analysis_id,),
        )
        analysis["factors"] = [dict(r) for r in cur.fetchall()]
        return analysis


def compute_scores(conn, analysis_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT category,
                      AVG(impact_score) AS avg_impact,
                      AVG(likelihood) AS avg_likelihood,
                      COUNT(*) AS factor_count
               FROM pestel_factor
               WHERE analysis_id = %s
               GROUP BY category""",
            (analysis_id,),
        )
        category_scores = {}
        for r in cur.fetchall():
            cat = r["category"]
            category_scores[cat] = {
                "avg_impact": float(r["avg_impact"]),
                "avg_likelihood": float(r["avg_likelihood"]),
                "factor_count": r["factor_count"],
            }

    scores = {}
    for cat in CATEGORIES:
        if cat in category_scores:
            cs = category_scores[cat]
            scores[cat] = round(cs["avg_impact"] * cs["avg_likelihood"], 2)
        else:
            scores[cat] = 0.0

    overall = round(sum(scores.values()) / len(CATEGORIES), 2) if scores else 0.0

    with conn.cursor() as cur:
        cur.execute(
            """UPDATE pestel_analysis
               SET political_score = %s, economic_score = %s, social_score = %s,
                   technological_score = %s, environmental_score = %s, legal_score = %s,
                   overall_score = %s
               WHERE id = %s""",
            (
                scores["political"], scores["economic"], scores["social"],
                scores["technological"], scores["environmental"], scores["legal"],
                overall, analysis_id,
            ),
        )
        conn.commit()

    logger.info("Computed PESTEL scores for analysis %s: overall=%s", analysis_id, overall)
    return {"analysis_id": analysis_id, "scores": scores, "overall": overall}


def suggest(conn, location_id: str) -> List[Dict[str, Any]]:
    suggested: List[Dict[str, Any]] = []

    # Political: threatcasting signals with policy type
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, name, severity, description
                   FROM threat
                   WHERE location_id = %s AND type = 'policy'
                   AND status IN ('active', 'monitored')
                   LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                suggested.append({
                    "category": "political",
                    "factor_type": "risk",
                    "title": f"Policy: {r['name']}",
                    "description": r.get("description") or "",
                    "impact_score": 7.0,
                    "likelihood": 0.6,
                    "evidence_source": {"table": "threat", "id": str(r["id"])},
                })
    except psycopg2.Error:
        conn.rollback()

    # Economic: market price observations
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT commodity, AVG(price) AS avg_price, COUNT(*) AS observations
                   FROM market_price_observation
                   WHERE location_id = %s
                   GROUP BY commodity
                   LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                suggested.append({
                    "category": "economic",
                    "factor_type": "opportunity",
                    "title": f"Market: {r['commodity']} (avg {float(r['avg_price']):.2f})",
                    "description": f"{r['observations']} price observations",
                    "impact_score": 6.0,
                    "likelihood": 0.7,
                    "evidence_source": {"table": "market_price_observation", "commodity": r["commodity"]},
                })
    except psycopg2.Error:
        conn.rollback()

    # Social: stakeholder feedback
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT stakeholder_group, COUNT(*) AS feedback_count,
                          AVG(CASE WHEN sentiment = 'positive' THEN 3
                                   WHEN sentiment = 'neutral' THEN 2
                                   ELSE 1 END) AS avg_sentiment
                   FROM stakeholder_feedback
                   WHERE location_id = %s
                   GROUP BY stakeholder_group
                   LIMIT 5""",
                (location_id,),
            )
            for r in cur.fetchall():
                sentiment = float(r["avg_sentiment"] or 2)
                factor_type = "strength" if sentiment >= 2.5 else "risk" if sentiment <= 1.5 else "neutral"
                suggested.append({
                    "category": "social",
                    "factor_type": factor_type,
                    "title": f"Community: {r['stakeholder_group']} ({r['feedback_count']} responses)",
                    "description": f"Avg sentiment: {sentiment:.1f}/3",
                    "impact_score": 5.0,
                    "likelihood": 0.8,
                    "evidence_source": {"table": "stakeholder_feedback", "group": r["stakeholder_group"]},
                })
    except psycopg2.Error:
        conn.rollback()

    # Technological: equipment and sensors
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(DISTINCT id) AS asset_count
                   FROM equipment_asset
                   WHERE location_id = %s""",
                (location_id,),
            )
            asset_count = (cur.fetchone() or {}).get("asset_count", 0) or 0
            if asset_count > 0:
                suggested.append({
                    "category": "technological",
                    "factor_type": "strength",
                    "title": f"Equipment: {asset_count} assets deployed",
                    "description": "Active equipment and sensor infrastructure",
                    "impact_score": 6.0,
                    "likelihood": 0.9,
                    "evidence_source": {"table": "equipment_asset", "count": asset_count},
                })
    except psycopg2.Error:
        conn.rollback()

    # Environmental: climate and soil data
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT AVG(temperature_avg) AS avg_temp,
                          SUM(rainfall_mm) AS total_rainfall,
                          COUNT(*) AS obs_count
                   FROM weather_observation
                   WHERE location_id = %s
                     AND observation_date >= CURRENT_DATE - INTERVAL '90 days'""",
                (location_id,),
            )
            weather = dict(cur.fetchone() or {})
            if weather.get("obs_count", 0) > 0:
                suggested.append({
                    "category": "environmental",
                    "factor_type": "neutral",
                    "title": f"Climate: {float(weather.get('avg_temp', 0) or 0):.1f}°C avg, {float(weather.get('total_rainfall', 0) or 0):.0f}mm rain (90d)",
                    "description": f"{weather['obs_count']} observations in last 90 days",
                    "impact_score": 5.0,
                    "likelihood": 0.8,
                    "evidence_source": {"table": "weather_observation", "period": "90d"},
                })
    except psycopg2.Error:
        conn.rollback()

    # Legal: certifications
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT certification_type, status, expiry_date::text
                   FROM organic_certification_record
                   WHERE location_id = %s
                   LIMIT 3""",
                (location_id,),
            )
            for r in cur.fetchall():
                factor_type = "strength" if r["status"] == "active" else "risk"
                suggested.append({
                    "category": "legal",
                    "factor_type": factor_type,
                    "title": f"Certification: {r['certification_type']} ({r['status']})",
                    "description": f"Expires: {r['expiry_date']}" if r["expiry_date"] else "",
                    "impact_score": 6.0,
                    "likelihood": 0.9,
                    "evidence_source": {"table": "organic_certification_record", "status": r["status"]},
                })
    except psycopg2.Error:
        conn.rollback()

    logger.info("Suggested %d PESTEL factors for location %s", len(suggested), location_id)
    return suggested


def render_markdown(analysis: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# PESTEL Analysis: {analysis.get('title', 'Untitled')}\n")
    lines.append(f"**Location:** {analysis.get('location_name', 'N/A')}")
    lines.append(f"**Period:** {analysis.get('period_start', 'N/A')} to {analysis.get('period_end', 'N/A')}")
    lines.append(f"**Status:** {analysis.get('status', 'draft')}")
    lines.append(f"**Overall Score:** {analysis.get('overall_score', 0)}/10\n")

    cat_labels = {
        "political": "Political",
        "economic": "Economic",
        "social": "Social",
        "technological": "Technological",
        "environmental": "Environmental",
        "legal": "Legal",
    }
    for cat in CATEGORIES:
        score = analysis.get(f"{cat}_score", 0)
        lines.append(f"## {cat_labels[cat]} — {score}/10\n")
        factors = [f for f in analysis.get("factors", []) if f["category"] == cat]
        if factors:
            for f in factors:
                lines.append(f"- **{f['title']}** ({f['factor_type']}, impact {f['impact_score']}, likelihood {f['likelihood']})")
                if f.get("description"):
                    lines.append(f"  {f['description']}")
        else:
            lines.append("- No factors assessed")
        lines.append("")

    return "\n".join(lines)


def render_cli(analysis: Dict[str, Any]) -> str:
    w = 78
    lines = []
    lines.append("=" * w)
    lines.append(f"  PESTEL ANALYSIS: {analysis.get('title', 'Untitled').upper()}")
    lines.append("=" * w)
    lines.append(f"  Location: {analysis.get('location_name', 'N/A')}")
    lines.append(f"  Period:   {analysis.get('period_start', 'N/A')} to {analysis.get('period_end', 'N/A')}")
    lines.append(f"  Status:   {analysis.get('status', 'draft')}")
    lines.append(f"  Overall:  {analysis.get('overall_score', 0)}/10")
    lines.append("-" * w)

    cat_labels = {
        "political": "POLITICAL", "economic": "ECONOMIC", "social": "SOCIAL",
        "technological": "TECHNOLOGICAL", "environmental": "ENVIRONMENTAL", "legal": "LEGAL",
    }
    for cat in CATEGORIES:
        score = analysis.get(f"{cat}_score", 0)
        lines.append(f"\n  {cat_labels[cat]} — {score}/10")
        factors = [f for f in analysis.get("factors", []) if f["category"] == cat]
        if factors:
            for f in factors:
                lines.append(f"    [{f['factor_type'].upper():^10}] {f['title']}")
                lines.append(f"             impact={f['impact_score']}  likelihood={f['likelihood']}")
                if f.get("description"):
                    for wrapped in textwrap.wrap(f["description"], w - 14):
                        lines.append(f"             {wrapped}")
        else:
            lines.append("    (no factors)")

    lines.append("\n" + "=" * w)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="PESTEL Analysis CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="Create PESTEL analysis")
    p.add_argument("--location-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--period-start", required=True)
    p.add_argument("--period-end", required=True)

    p = sub.add_parser("add-factor", help="Add a PESTEL factor")
    p.add_argument("--analysis-id", required=True)
    p.add_argument("--category", required=True, choices=list(CATEGORIES))
    p.add_argument("--factor-type", required=True, choices=list(FACTOR_TYPES))
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--impact", type=float, default=5.0)
    p.add_argument("--likelihood", type=float, default=0.5)

    p = sub.add_parser("list", help="List PESTEL analyses")
    p.add_argument("--location-id")

    p = sub.add_parser("get", help="Get a PESTEL analysis")
    p.add_argument("--analysis-id", required=True)

    p = sub.add_parser("compute", help="Compute PESTEL scores")
    p.add_argument("--analysis-id", required=True)

    p = sub.add_parser("suggest", help="Suggest PESTEL factors from platform data")
    p.add_argument("--location-id", required=True)

    p = sub.add_parser("export", help="Export analysis as markdown")
    p.add_argument("--analysis-id", required=True)

    args = parser.parse_args()
    conn = get_db()
    try:
        if args.command == "create":
            result = create_analysis(conn, args.location_id, args.title, args.period_start, args.period_end)
        elif args.command == "add-factor":
            result = add_factor(conn, args.analysis_id, args.category, args.factor_type,
                                args.title, args.description, args.impact, args.likelihood)
        elif args.command == "list":
            result = list_analyses(conn, args.location_id)
        elif args.command == "get":
            result = get_analysis(conn, args.analysis_id)
        elif args.command == "compute":
            result = compute_scores(conn, args.analysis_id)
        elif args.command == "suggest":
            result = suggest(conn, args.location_id)
        elif args.command == "export":
            analysis = get_analysis(conn, args.analysis_id)
            if analysis:
                print(render_markdown(analysis))
                return
            result = {"error": "analysis not found"}
        else:
            result = {"error": "unknown command"}
        print(json.dumps(result, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
