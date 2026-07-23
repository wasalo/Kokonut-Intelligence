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

from services.common.database import get_db


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
        elif args.command == "factor":
            out = _cmd_factor(args, conn)
        elif args.command == "tows":
            out = _cmd_tows(args, conn)
        elif args.command == "competitor":
            out = _cmd_competitor(args, conn)
        elif args.command == "temporal":
            out = _cmd_temporal(args, conn)
        elif args.command == "action":
            out = _cmd_action(args, conn)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def _cmd_factor(args, conn):
    from services.analytics import swot_enhanced
    if args.factor_command == "create":
        return swot_enhanced.create_factor(
            conn, args.swot_id, args.factor_type, args.category,
            args.description, priority=args.priority, confidence=args.confidence,
            source=args.source,
        )
    elif args.factor_command == "list":
        return swot_enhanced.list_factors(
            conn, args.swot_id, factor_type=args.factor_type,
            classification=args.classification,
        )
    elif args.factor_command == "delete":
        return {"deleted": swot_enhanced.delete_factor(conn, args.factor_id)}
    return {}


def _cmd_tows(args, conn):
    from services.analytics import swot_enhanced
    if args.tows_command == "generate":
        return swot_enhanced.generate_tows(conn, args.swot_id)
    elif args.tows_command == "list":
        return swot_enhanced.get_tows(conn, args.swot_id)
    elif args.tows_command == "approve":
        return swot_enhanced.approve_tows(conn, args.strategy_id, args.approved_by)
    elif args.tows_command == "fit":
        return swot_enhanced.compute_strategic_fit(conn, args.swot_id)
    return {}


def _cmd_competitor(args, conn):
    from services.analytics import swot_enhanced
    if args.competitor_command == "create":
        return swot_enhanced.create_competitor(
            conn, args.location_id, args.name,
            competitor_type=args.type,
            strengths=args.strengths, weaknesses=args.weaknesses,
            competitive_threat_level=args.threat_level,
        )
    elif args.competitor_command == "list":
        return swot_enhanced.list_competitors(conn, args.location_id)
    return {}


def _cmd_temporal(args, conn):
    from services.analytics import swot_enhanced
    if args.temporal_command == "snapshot":
        return swot_enhanced.snapshot_temporal(
            conn, args.swot_id, change_summary=args.summary,
        )
    elif args.temporal_command == "list":
        return swot_enhanced.list_temporal(conn, args.swot_id)
    return {}


def _cmd_action(args, conn):
    from services.analytics import swot_enhanced
    if args.action_command == "link":
        return swot_enhanced.link_action(
            conn, args.swot_id, args.description,
            target_type=args.target_type, factor_id=args.factor_id,
            strategy_id=args.strategy_id,
        )
    elif args.action_command == "list":
        return swot_enhanced.list_actions(conn, args.swot_id)
    return {}


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

    # factor subcommands
    f = sub.add_parser("factor")
    fs = f.add_subparsers(dest="factor_command", required=True)
    fc = fs.add_parser("create")
    fc.add_argument("--swot-id", required=True)
    fc.add_argument("--factor-type", required=True, choices=["strength", "weakness", "opportunity", "threat"])
    fc.add_argument("--category", required=True)
    fc.add_argument("--description", required=True)
    fc.add_argument("--priority", type=int, default=0)
    fc.add_argument("--confidence", type=float, default=0.5)
    fc.add_argument("--source", default=None)
    fl = fs.add_parser("list")
    fl.add_argument("--swot-id", required=True)
    fl.add_argument("--factor-type", default=None)
    fl.add_argument("--classification", default=None)
    fd = fs.add_parser("delete")
    fd.add_argument("--factor-id", required=True)

    # tows subcommands
    t = sub.add_parser("tows")
    ts = t.add_subparsers(dest="tows_command", required=True)
    tg = ts.add_parser("generate")
    tg.add_argument("--swot-id", required=True)
    tl = ts.add_parser("list")
    tl.add_argument("--swot-id", required=True)
    ta = ts.add_parser("approve")
    ta.add_argument("--strategy-id", required=True)
    ta.add_argument("--approved-by", required=True)
    tf = ts.add_parser("fit")
    tf.add_argument("--swot-id", required=True)

    # competitor subcommands
    comp = sub.add_parser("competitor")
    comps = comp.add_subparsers(dest="competitor_command", required=True)
    cc = comps.add_parser("create")
    cc.add_argument("--location-id", required=True)
    cc.add_argument("--name", required=True)
    cc.add_argument("--type", default=None)
    cc.add_argument("--strengths", nargs="*", default=[])
    cc.add_argument("--weaknesses", nargs="*", default=[])
    cc.add_argument("--threat-level", default="moderate")
    cl = comps.add_parser("list")
    cl.add_argument("--location-id", required=True)

    # temporal subcommands
    tmp = sub.add_parser("temporal")
    tmps = tmp.add_subparsers(dest="temporal_command", required=True)
    tsnap = tmps.add_parser("snapshot")
    tsnap.add_argument("--swot-id", required=True)
    tsnap.add_argument("--summary", default=None)
    tlist = tmps.add_parser("list")
    tlist.add_argument("--swot-id", required=True)

    # action subcommands
    act = sub.add_parser("action")
    acts = act.add_subparsers(dest="action_command", required=True)
    al = acts.add_parser("link")
    al.add_argument("--swot-id", required=True)
    al.add_argument("--description", required=True)
    al.add_argument("--target-type", default="recommendation")
    al.add_argument("--factor-id", default=None)
    al.add_argument("--strategy-id", default=None)
    alst = acts.add_parser("list")
    alst.add_argument("--swot-id", required=True)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
