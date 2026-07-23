"""Publics & Market Segmentation service."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db
from services.common.logging import get_logger

logger = get_logger(__name__)

PUBLIC_TYPES = (
    "financial", "media", "government", "citizen_action",
    "local_community", "general_public", "employees", "academic", "industry",
)
SEGMENT_TYPES = ("consumer", "business", "government", "export", "reseller")
STANCES = ("supportive", "neutral", "opposed")


def add_public(
    conn,
    location_id: str,
    public_type: str,
    name: str,
    description: str = "",
    influence_score: float = 5.0,
    interest_score: float = 5.0,
    stance: str = "neutral",
    evidence_source: Optional[Dict] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if public_type not in PUBLIC_TYPES:
        raise ValueError(f"public_type must be one of {PUBLIC_TYPES}")
    if stance not in STANCES:
        raise ValueError(f"stance must be one of {STANCES}")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO stakeholder_public
               (location_id, public_type, name, description, influence_score,
                interest_score, stance, evidence_source, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, public_type, name, influence_score, interest_score, stance, status, created_at""",
            (
                location_id, public_type, name, description, influence_score,
                interest_score, stance, json.dumps(evidence_source or {}), created_by,
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
        logger.info("Added public %s (%s) for %s", row["id"], public_type, location_id)
        return row


def list_publics(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                """SELECT sp.*, l.name AS location_name
                   FROM stakeholder_public sp
                   LEFT JOIN location l ON l.id = sp.location_id
                   WHERE sp.location_id = %s
                   ORDER BY sp.influence_score DESC""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT sp.*, l.name AS location_name
                   FROM stakeholder_public sp
                   LEFT JOIN location l ON l.id = sp.location_id
                   ORDER BY sp.influence_score DESC"""
            )
        return [dict(r) for r in cur.fetchall()]


def update_stance(conn, public_id: str, stance: str, notes: str = "") -> Dict[str, Any]:
    if stance not in STANCES:
        raise ValueError(f"stance must be one of {STANCES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """UPDATE stakeholder_public
               SET stance = %s, stance_notes = %s, updated_at = now()
               WHERE id = %s
               RETURNING id, name, stance, stance_notes""",
            (stance, notes, public_id),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else {}


def remove_public(conn, public_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM stakeholder_public WHERE id = %s", (public_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def create_segment(
    conn,
    location_id: str,
    segment_type: str,
    name: str,
    description: str = "",
    demand_pattern: str = "",
    pricing_range: Optional[Dict] = None,
    channel_preferences: Optional[List] = None,
    size_estimate: Optional[float] = None,
    size_unit: str = "",
    evidence_source: Optional[Dict] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if segment_type not in SEGMENT_TYPES:
        raise ValueError(f"segment_type must be one of {SEGMENT_TYPES}")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO market_segment
               (location_id, segment_type, name, description, demand_pattern,
                pricing_range, channel_preferences, size_estimate, size_unit,
                evidence_source, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, segment_type, name, size_estimate, status, created_at""",
            (
                location_id, segment_type, name, description, demand_pattern,
                json.dumps(pricing_range or {}), json.dumps(channel_preferences or []),
                size_estimate, size_unit, json.dumps(evidence_source or {}), created_by,
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
        logger.info("Created segment %s (%s) for %s", row["id"], segment_type, location_id)
        return row


def list_segments(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                """SELECT ms.*, l.name AS location_name
                   FROM market_segment ms
                   LEFT JOIN location l ON l.id = ms.location_id
                   WHERE ms.location_id = %s
                   ORDER BY ms.segment_type, ms.size_estimate DESC NULLS LAST""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT ms.*, l.name AS location_name
                   FROM market_segment ms
                   LEFT JOIN location l ON l.id = ms.location_id
                   ORDER BY ms.segment_type, ms.size_estimate DESC NULLS LAST"""
            )
        return [dict(r) for r in cur.fetchall()]


def update_segment(conn, segment_id: str, **kwargs) -> Dict[str, Any]:
    allowed = {"name", "description", "demand_pattern", "pricing_range",
               "channel_preferences", "size_estimate", "size_unit"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return {}

    set_parts = []
    params = []
    for k, v in updates.items():
        if k in ("pricing_range", "channel_preferences"):
            set_parts.append(f"{k} = %s")
            params.append(json.dumps(v))
        else:
            set_parts.append(f"{k} = %s")
            params.append(v)
    params.append(segment_id)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""UPDATE market_segment SET {', '.join(set_parts)}, updated_at = now()
                WHERE id = %s RETURNING id, name, segment_type""",
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else {}


def map_demand(conn, segment_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM market_segment WHERE id = %s", (segment_id,))
        seg = cur.fetchone()
        if not seg:
            return {"error": "segment not found"}
        seg = dict(seg)

        cur.execute(
            """SELECT COUNT(*) AS signal_count, SUM(quantity) AS total_demand
               FROM buyer_demand_signal
               WHERE location_id = %s""",
            (seg["location_id"],),
        )
        demand = dict(cur.fetchone() or {})

        cur.execute(
            """SELECT commodity, AVG(price) AS avg_price, COUNT(*) AS observations
               FROM market_price_observation
               WHERE location_id = %s
               GROUP BY commodity""",
            (seg["location_id"],),
        )
        prices = [dict(r) for r in cur.fetchall()]

        return {
            "segment": seg,
            "demand": demand,
            "prices": prices,
        }


def influence_interest_matrix(conn, location_id: str) -> Dict[str, Any]:
    publics = list_publics(conn, location_id)
    matrix = {
        "key_player": [],     # high influence, high interest
        "keep_satisfied": [],  # high influence, low interest
        "keep_informed": [],   # low influence, high interest
        "monitor": [],         # low influence, low interest
    }
    for p in publics:
        inf = float(p.get("influence_score", 5))
        int_ = float(p.get("interest_score", 5))
        if inf >= 7 and int_ >= 7:
            matrix["key_player"].append(p)
        elif inf >= 7:
            matrix["keep_satisfied"].append(p)
        elif int_ >= 7:
            matrix["keep_informed"].append(p)
        else:
            matrix["monitor"].append(p)
    return matrix


def suggest(conn, location_id: str) -> Dict[str, List[Dict]]:
    publics_suggested: List[Dict] = []
    segments_suggested: List[Dict] = []

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT partner_type, COUNT(*) AS cnt
                   FROM partner WHERE location_id = %s
                   GROUP BY partner_type""",
                (location_id,),
            )
            type_map = {
                "cooperative": ("local_community", "supportive"),
                "buyer": ("industry", "supportive"),
                "government": ("government", "neutral"),
                "ngo": ("citizen_action", "supportive"),
                "investor": ("financial", "supportive"),
                "academic": ("academic", "neutral"),
            }
            for r in cur.fetchall():
                ptype = type_map.get(r["partner_type"], ("general_public", "neutral"))
                publics_suggested.append({
                    "public_type": ptype[0],
                    "name": f"{r['partner_type'].title()} partners ({r['cnt']})",
                    "influence_score": 6.0,
                    "interest_score": 7.0,
                    "stance": ptype[1],
                    "evidence_source": {"table": "partner", "partner_type": r["partner_type"]},
                })
    except psycopg2.Error:
        conn.rollback()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT commodity, COUNT(*) AS signals, AVG(price) AS avg_price
                   FROM buyer_demand_signal
                   WHERE location_id = %s
                   GROUP BY commodity""",
                (location_id,),
            )
            for r in cur.fetchall():
                segments_suggested.append({
                    "segment_type": "business",
                    "name": f"{r['commodity']} buyers",
                    "demand_pattern": "recurring",
                    "pricing_range": {"avg": float(r["avg_price"] or 0)},
                    "size_estimate": float(r["signals"] or 0),
                    "evidence_source": {"table": "buyer_demand_signal", "commodity": r["commodity"]},
                })
    except psycopg2.Error:
        conn.rollback()

    return {"publics": publics_suggested, "segments": segments_suggested}


def main():
    parser = argparse.ArgumentParser(description="Publics & Market Segmentation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-public", help="Add a stakeholder public")
    p.add_argument("--location-id", required=True)
    p.add_argument("--type", required=True, dest="public_type", choices=list(PUBLIC_TYPES))
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--influence", type=float, default=5.0)
    p.add_argument("--interest", type=float, default=5.0)
    p.add_argument("--stance", default="neutral", choices=list(STANCES))

    p = sub.add_parser("list", help="List publics")
    p.add_argument("--location-id")

    p = sub.add_parser("update-stance", help="Update stance")
    p.add_argument("--public-id", required=True)
    p.add_argument("--stance", required=True, choices=list(STANCES))
    p.add_argument("--notes", default="")

    p = sub.add_parser("create-segment", help="Create market segment")
    p.add_argument("--location-id", required=True)
    p.add_argument("--type", required=True, dest="segment_type", choices=list(SEGMENT_TYPES))
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--demand-pattern", default="")
    p.add_argument("--size-estimate", type=float)

    p = sub.add_parser("list-segments", help="List segments")
    p.add_argument("--location-id")

    p = sub.add_parser("map-demand", help="Map demand for segment")
    p.add_argument("--segment-id", required=True)

    p = sub.add_parser("matrix", help="Influence/interest matrix")
    p.add_argument("--location-id", required=True)

    p = sub.add_parser("suggest", help="Suggest from platform data")
    p.add_argument("--location-id", required=True)

    args = parser.parse_args()
    conn = get_db()
    try:
        if args.command == "add-public":
            result = add_public(conn, args.location_id, args.public_type, args.name,
                                args.description, args.influence, args.interest, args.stance)
        elif args.command == "list":
            result = list_publics(conn, args.location_id)
        elif args.command == "update-stance":
            result = update_stance(conn, args.public_id, args.stance, args.notes)
        elif args.command == "create-segment":
            result = create_segment(conn, args.location_id, args.segment_type, args.name,
                                    args.description, args.demand_pattern,
                                    size_estimate=args.size_estimate)
        elif args.command == "list-segments":
            result = list_segments(conn, args.location_id)
        elif args.command == "map-demand":
            result = map_demand(conn, args.segment_id)
        elif args.command == "matrix":
            result = influence_interest_matrix(conn, args.location_id)
        elif args.command == "suggest":
            result = suggest(conn, args.location_id)
        else:
            result = {"error": "unknown command"}
        print(json.dumps(result, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
