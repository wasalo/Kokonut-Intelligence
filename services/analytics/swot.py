"""SWOT analysis service (business-plan section).

Stores structured Strengths/Weaknesses/Opportunities/Threats for an
organization or a single location, and can *suggest* threats/opportunities
from existing threatcasting + narrative data. Best-effort: any source that
is unavailable degrades to an empty list rather than raising.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db


def _entity(org_id: Optional[str], location_id: Optional[str]):
    if org_id and not location_id:
        return "organization", org_id
    if location_id and not org_id:
        return "location", location_id
    raise ValueError("provide exactly one of org_id or location_id")


def create(
    conn, org_id: Optional[str] = None, location_id: Optional[str] = None,
    strengths: Optional[List[str]] = None, weaknesses: Optional[List[str]] = None,
    opportunities: Optional[List[str]] = None, threats: Optional[List[str]] = None,
    generated_from: Optional[List[str]] = None, created_by: Optional[str] = None,
) -> Dict[str, Any]:
    entity_type, entity_id = _entity(org_id, location_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO swot_analysis (
                organization_id, location_id, entity_type, entity_id,
                strengths, weaknesses, opportunities, threats, generated_from, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, entity_type, entity_id, status
            """,
            (
                org_id, location_id, entity_type, entity_id,
                strengths or [], weaknesses or [], opportunities or [], threats or [],
                generated_from or [], created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_swot(
    conn, org_id: Optional[str] = None, location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if org_id and not location_id:
        where, params = "organization_id = %s", [org_id]
    elif location_id and not org_id:
        where, params = "location_id = %s", [location_id]
    else:
        raise ValueError("provide exactly one of org_id or location_id")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT id, entity_type, entity_id, status, created_at FROM swot_analysis WHERE {where} ORDER BY created_at DESC",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get(conn, swot_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM swot_analysis WHERE id = %s", (swot_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _location_filter(conn, org_id: Optional[str], location_id: Optional[str]):
    """Return the SQL location filter + params for org/location scope."""
    if location_id and not org_id:
        return "l.id = %s", [location_id]
    if org_id and not location_id:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location WHERE organization_id = %s", (org_id,))
            ids = [r[0] for r in cur.fetchall()]
        if not ids:
            return "1 = 0", []
        return "l.id = ANY(%s)", [ids]
    raise ValueError("provide exactly one of org_id or location_id")


def suggest(
    conn, org_id: Optional[str] = None, location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Best-effort SWOT suggestions from existing data."""
    generated_from: List[str] = []
    threats: List[str] = []
    opportunities: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []

    filt, params = _location_filter(conn, org_id, location_id)
    # threats from threatcasting
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT t.threat_name FROM threat t
                JOIN location l ON l.id = t.location_id
                WHERE {filt} AND t.is_active = TRUE
                ORDER BY t.severity_potential DESC, t.probability DESC
                LIMIT 20
                """,
                params,
            )
            threats = [r[0] for r in cur.fetchall()]
        if threats:
            generated_from.append("threatcasting.threat")
    except psycopg2.Error:
        pass

    # opportunities from desirable/baseline narratives
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT n.title FROM threat_narrative n
                JOIN location l ON l.id = n.location_id
                WHERE {filt} AND n.narrative_type IN ('desirable', 'baseline')
                ORDER BY n.created_at DESC LIMIT 20
                """,
                params,
            )
            opportunities = [r[0] for r in cur.fetchall()]
        if opportunities:
            generated_from.append("threatcasting.narrative")
    except psycopg2.Error:
        pass

    # strengths/weaknesses from CRISP dimension health (best-effort)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.dimension, a.rating_band FROM crisp_risk_assessment a
                JOIN location l ON l.id = a.location_id
                WHERE {filt} AND a.status = 'active'
                ORDER BY a.assessed_at DESC
                """,
                params,
            )
            for dim, band in cur.fetchall():
                if band in ("AAA", "AA", "A"):
                    strengths.append(f"{dim} risk rated {band}")
                elif band in ("C", "D"):
                    weaknesses.append(f"{dim} risk rated {band}")
        if strengths or weaknesses:
            generated_from.append("crisp.risk")
    except psycopg2.Error:
        pass

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "threats": threats,
        "generated_from": generated_from,
    }


def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "create":
            out = create(
                conn, args.org_id, args.location_id,
                strengths=args.strengths, weaknesses=args.weaknesses,
                opportunities=args.opportunities, threats=args.threats,
                created_by=args.created_by,
            )
        elif args.command == "list":
            out = list_swot(conn, args.org_id, args.location_id)
        elif args.command == "get":
            out = get(conn, args.swot_id)
        elif args.command == "suggest":
            out = suggest(conn, args.org_id, args.location_id)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="SWOT analysis (business plan)")
    p.add_argument("--org-id", default=None)
    p.add_argument("--location-id", default=None)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create")
    c.add_argument("--strengths", nargs="*", default=[])
    c.add_argument("--weaknesses", nargs="*", default=[])
    c.add_argument("--opportunities", nargs="*", default=[])
    c.add_argument("--threats", nargs="*", default=[])
    c.add_argument("--created-by", default=None)
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("--swot-id", required=True)
    sub.add_parser("suggest")
    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
