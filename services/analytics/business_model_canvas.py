"""Business Model Canvas service.

Stores the 9-building-block Osterwalder/Painer Business Model Canvas
per location or organization, with Value Proposition Canvas support
(customer jobs, pain points, gain creators) and auto-suggestion from
existing platform data.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db

# The 9 BMC building blocks in canonical order
BMC_BLOCKS = [
    "key_partners", "key_activities", "key_resources",
    "value_propositions", "customer_relationships", "channels",
    "customer_segments", "revenue_streams", "cost_structure",
]


def _entity(org_id: Optional[str], location_id: Optional[str]):
    if org_id and not location_id:
        return "organization", org_id
    if location_id and not org_id:
        return "location", location_id
    raise ValueError("provide exactly one of org_id or location_id")


def create(
    conn, location_id: Optional[str] = None, org_id: Optional[str] = None,
    canvas_name: str = "Primary Canvas", description: Optional[str] = None,
    fiscal_year: Optional[int] = None, tags: Optional[List[str]] = None,
    blocks: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    entity_type, entity_id = _entity(org_id, location_id)
    block_values = {b: (blocks or {}).get(b, [] if b != "cost_structure" else {}) for b in BMC_BLOCKS}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO business_model_canvas (
                location_id, organization_id, entity_type, entity_id,
                key_partners, key_activities, key_resources,
                value_propositions, customer_relationships, channels,
                customer_segments, revenue_streams, cost_structure,
                canvas_name, description, fiscal_year, tags, created_by
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            RETURNING id, entity_type, entity_id, status, version
            """,
            (
                location_id, org_id, entity_type, entity_id,
                json.dumps(block_values["key_partners"]),
                json.dumps(block_values["key_activities"]),
                json.dumps(block_values["key_resources"]),
                json.dumps(block_values["value_propositions"]),
                json.dumps(block_values["customer_relationships"]),
                json.dumps(block_values["channels"]),
                json.dumps(block_values["customer_segments"]),
                json.dumps(block_values["revenue_streams"]),
                json.dumps(block_values["cost_structure"]),
                canvas_name, description, fiscal_year,
                tags or [], created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def create_from_data(
    conn, location_id: Optional[str] = None, org_id: Optional[str] = None,
    canvas_name: str = "Primary Canvas (auto)", description: Optional[str] = None,
    fiscal_year: Optional[int] = None, tags: Optional[List[str]] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """One-click BMC: derive blocks from existing platform data and persist.

    Reads the best-effort suggestions from :func:`suggest` (federation,
    cooperative, supplier, process_map, sensor/energy/cooperative assets,
    impact_claim, channels, buyer_segment, revenue_event, expense_event,
    stakeholder_feedback) and writes a fully-populated draft canvas in a
    single call. Returns the created canvas plus the data sources used.
    """
    if not location_id and not org_id:
        raise ValueError("provide exactly one of org_id or location_id")
    suggestion = suggest(conn, location_id) if location_id else {"blocks": {b: [] if b != "cost_structure" else {} for b in BMC_BLOCKS}, "generated_from": []}
    # suggest() runs several independent read queries; a failure in one can abort
    # the shared transaction, so clear any aborted-state before the write.
    try:
        conn.rollback()
    except psycopg2.Error:
        pass
    canvas = create(
        conn,
        location_id=location_id,
        org_id=org_id,
        canvas_name=canvas_name,
        description=description,
        fiscal_year=fiscal_year,
        tags=tags or ["auto-generated"],
        blocks=suggestion["blocks"],
        created_by=created_by,
    )
    return {
        "canvas": canvas,
        "generated_from": suggestion["generated_from"],
        "populated_blocks": [b for b, v in suggestion["blocks"].items() if v],
    }


def list_canvas(
    conn, location_id: Optional[str] = None, org_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if location_id and not org_id:
        where, params = "bmc.location_id = %s", [location_id]
    elif org_id and not location_id:
        where, params = "bmc.organization_id = %s", [org_id]
    else:
        raise ValueError("provide exactly one of org_id or location_id")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT bmc.id, bmc.entity_type, bmc.entity_id, bmc.canvas_name,
                   bmc.status, bmc.version, bmc.health_score, bmc.tags,
                   bmc.created_at
            FROM business_model_canvas bmc
            WHERE {where}
            ORDER BY bmc.created_at DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get(conn, canvas_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM business_model_canvas WHERE id = %s", (canvas_id,))
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        # Attach child entities
        cur.execute(
            "SELECT * FROM customer_job WHERE canvas_id = %s ORDER BY importance_rank",
            (canvas_id,),
        )
        result["jobs"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT * FROM pain_point WHERE canvas_id = %s ORDER BY severity",
            (canvas_id,),
        )
        result["pain_points"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT * FROM gain_creator WHERE canvas_id = %s ORDER BY gain_type",
            (canvas_id,),
        )
        result["gain_creators"] = [dict(r) for r in cur.fetchall()]
        return result


def update_block(
    conn, canvas_id: str, block_name: str, items: Any,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    if block_name not in BMC_BLOCKS:
        raise ValueError(f"invalid block: {block_name}; must be one of {BMC_BLOCKS}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            UPDATE business_model_canvas
            SET {block_name} = %s, updated_at = NOW(), updated_by = %s
            WHERE id = %s
            RETURNING id, version
            """,
            (json.dumps(items), updated_by, canvas_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"canvas {canvas_id} not found")
        conn.commit()
        return dict(row)


def create_version(
    conn, canvas_id: str, changes: Optional[str] = None,
    change_reason: Optional[str] = None, created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Get current canvas as snapshot
        cur.execute("SELECT * FROM business_model_canvas WHERE id = %s", (canvas_id,))
        canvas = cur.fetchone()
        if not canvas:
            raise ValueError(f"canvas {canvas_id} not found")
        canvas_dict = dict(canvas)
        # Build snapshot (strip non-serializable fields)
        snapshot = {b: canvas_dict.get(b) for b in BMC_BLOCKS}
        snapshot["canvas_name"] = canvas_dict.get("canvas_name")
        snapshot["fiscal_year"] = canvas_dict.get("fiscal_year")
        # Determine next version
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_ver FROM canvas_version WHERE canvas_id = %s",
            (canvas_id,),
        )
        next_version = cur.fetchone()["next_ver"]
        cur.execute(
            """
            INSERT INTO canvas_version (canvas_id, version, snapshot, changes, change_reason, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, canvas_id, version
            """,
            (canvas_id, next_version, json.dumps(snapshot), changes, change_reason, created_by),
        )
        row = cur.fetchone()
        # Bump canvas version
        cur.execute(
            "UPDATE business_model_canvas SET version = %s WHERE id = %s",
            (next_version, canvas_id),
        )
        conn.commit()
        return dict(row)


def list_versions(conn, canvas_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, version, changes, change_reason, created_at, created_by
            FROM canvas_version WHERE canvas_id = %s ORDER BY version DESC
            """,
            (canvas_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def _location_filter(conn, org_id: Optional[str], location_id: Optional[str]):
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
    conn, location_id: str,
) -> Dict[str, Any]:
    """Best-effort BMC suggestions from existing platform data."""
    generated_from: List[str] = []
    blocks: Dict[str, Any] = {b: [] for b in BMC_BLOCKS}
    blocks["cost_structure"] = {}

    # Key Partners from federation nodes + cooperatives + suppliers
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, 'federation' AS ptype FROM federation_node
                WHERE status = 'active'
                UNION ALL
                SELECT name, 'cooperative' FROM cooperative WHERE location_id = %s
                UNION ALL
                SELECT supplier_name, 'supplier' FROM supplier_profile WHERE location_id = %s
                LIMIT 20
                """,
                (location_id, location_id),
            )
            partners = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        if partners:
            blocks["key_partners"] = partners
            generated_from.append("federation/cooperative/supplier")
    except psycopg2.Error:
        pass

    # Key Activities from process_map
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT process_name, process_category FROM process_map
                WHERE is_active = TRUE
                ORDER BY sort_order LIMIT 20
                """,
            )
            activities = [{"name": r[0], "category": r[1]} for r in cur.fetchall()]
        if activities:
            blocks["key_activities"] = activities
            generated_from.append("process_map")
    except psycopg2.Error:
        pass

    # Key Resources from sensor_device + energy_source + cooperative_asset
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT device_name, 'sensor' AS rtype FROM sensor_device
                WHERE location_id = %s AND status = 'active'
                UNION ALL
                SELECT name, 'energy' FROM energy_source WHERE location_id = %s
                UNION ALL
                SELECT name, 'cooperative_asset' FROM cooperative_asset ca
                JOIN cooperative c ON c.id = ca.cooperative_id
                WHERE c.location_id = %s
                LIMIT 20
                """,
                (location_id, location_id, location_id),
            )
            resources = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        if resources:
            blocks["key_resources"] = resources
            generated_from.append("sensor/energy/cooperative_asset")
    except psycopg2.Error:
        pass

    # Value Propositions from impact_claim
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT claim_type, claim_description FROM impact_claim
                WHERE location_id = %s AND status IN ('verified', 'published')
                ORDER BY created_at DESC LIMIT 10
                """,
                (location_id,),
            )
            vps = [{"type": r[0], "description": r[1]} for r in cur.fetchall()]
        if vps:
            blocks["value_propositions"] = vps
            generated_from.append("impact_claim")
    except psycopg2.Error:
        pass

    # Channels from content_delivery
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT channel FROM content_delivery
                WHERE location_id = %s
                LIMIT 10
                """,
                (location_id,),
            )
            channels = [{"name": r[0]} for r in cur.fetchall()]
        if channels:
            blocks["channels"] = channels
            generated_from.append("content_delivery")
    except psycopg2.Error:
        pass

    # Customer Segments from buyer_segment
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT segment_name, segment_type FROM buyer_segment
                WHERE location_id = %s
                LIMIT 10
                """,
                (location_id,),
            )
            segments = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        if segments:
            blocks["customer_segments"] = segments
            generated_from.append("buyer_segment")
    except psycopg2.Error:
        pass

    # Revenue Streams from revenue_event (aggregated by type)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT revenue_type, SUM(amount_usd) AS total
                FROM revenue_event
                WHERE location_id = %s
                GROUP BY revenue_type
                LIMIT 10
                """,
                (location_id,),
            )
            streams = [{"type": r[0], "total_usd": float(r[1] or 0)} for r in cur.fetchall()]
        if streams:
            blocks["revenue_streams"] = streams
            generated_from.append("revenue_event")
    except psycopg2.Error:
        pass

    # Cost Structure from expense_event (aggregated by category)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category, SUM(amount_usd) AS total
                FROM expense_event
                WHERE location_id = %s
                GROUP BY category
                LIMIT 20
                """,
                (location_id,),
            )
            costs = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        if costs:
            blocks["cost_structure"] = costs
            generated_from.append("expense_event")
    except psycopg2.Error:
        pass

    # Customer Relationships from stakeholder_feedback (aggregated sentiment)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sentiment, COUNT(*) AS cnt
                FROM stakeholder_feedback
                WHERE location_id = %s
                GROUP BY sentiment
                """,
                (location_id,),
            )
            sentiments = {r[0]: r[1] for r in cur.fetchall()}
        if sentiments:
            blocks["customer_relationships"] = [{"feedback_sentiment": sentiments}]
            generated_from.append("stakeholder_feedback")
    except psycopg2.Error:
        pass

    return {
        "blocks": blocks,
        "generated_from": generated_from,
    }


def compute_health(conn, canvas_id: str) -> Dict[str, Any]:
    """Compute composite health score (0-100) across all 9 BMC blocks.

    Scoring: each populated block adds ~11.1 points. Quality modifiers:
    - Blocks with non-empty content: full points
    - Blocks with structured data (lists with >1 item): bonus 2 points
    - Value Propositions linked to customer jobs: bonus 5 points
    - Cost Structure with actual data: bonus 3 points
    """
    canvas = get(conn, canvas_id)
    if not canvas:
        raise ValueError(f"canvas {canvas_id} not found")

    base_per_block = 100.0 / 9  # ~11.11
    score = 0.0
    breakdown = {}

    for block in BMC_BLOCKS:
        value = canvas.get(block)
        block_score = 0.0
        if value is not None:
            if isinstance(value, list) and len(value) > 0:
                block_score = base_per_block
                if len(value) > 1:
                    block_score += 2  # bonus for multiple items
            elif isinstance(value, dict) and value:
                block_score = base_per_block
                if len(value) > 1:
                    block_score += 2
            elif isinstance(value, str) and value.strip():
                block_score = base_per_block
        breakdown[block] = round(block_score, 1)
        score += block_score

    # Bonus: value propositions linked to jobs
    jobs = canvas.get("jobs", [])
    vps = canvas.get("value_propositions", [])
    if jobs and vps:
        score += 5
        breakdown["vpc_link_bonus"] = 5

    # Bonus: cost structure has actual data
    cs = canvas.get("cost_structure", {})
    if cs and isinstance(cs, dict) and any(v > 0 for v in cs.values() if isinstance(v, (int, float))):
        score += 3
        breakdown["cost_data_bonus"] = 3

    score = min(100.0, round(score, 1))

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE business_model_canvas
            SET health_score = %s, health_score_breakdown = %s, health_score_computed_at = NOW()
            WHERE id = %s
            """,
            (score, json.dumps(breakdown), canvas_id),
        )
        conn.commit()

    return {"health_score": score, "breakdown": breakdown}


def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "create":
            out = create(
                conn, location_id=args.location_id, org_id=args.org_id,
                canvas_name=args.canvas_name, description=args.description,
                fiscal_year=args.fiscal_year, tags=args.tags,
                created_by=args.created_by,
            )
        elif args.command == "create-from-data":
            out = create_from_data(
                conn, location_id=args.location_id, org_id=args.org_id,
                canvas_name=args.canvas_name, description=args.description,
                fiscal_year=args.fiscal_year, tags=args.tags,
                created_by=args.created_by,
            )
        elif args.command == "list":
            out = list_canvas(conn, location_id=args.location_id, org_id=args.org_id)
        elif args.command == "get":
            out = get(conn, args.canvas_id)
        elif args.command == "update-block":
            items = json.loads(args.items) if args.items else []
            out = update_block(conn, args.canvas_id, args.block, items, updated_by=args.updated_by)
        elif args.command == "version":
            out = create_version(
                conn, args.canvas_id, changes=args.changes,
                change_reason=args.change_reason, created_by=args.created_by,
            )
        elif args.command == "list-versions":
            out = list_versions(conn, args.canvas_id)
        elif args.command == "suggest":
            out = suggest(conn, args.location_id)
        elif args.command == "health":
            out = compute_health(conn, args.canvas_id)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Business Model Canvas (BMC)")
    p.add_argument("--location-id", default=None)
    p.add_argument("--org-id", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create")
    c.add_argument("--canvas-name", default="Primary Canvas")
    c.add_argument("--description", default=None)
    c.add_argument("--fiscal-year", type=int, default=None)
    c.add_argument("--tags", nargs="*", default=[])
    c.add_argument("--created-by", default=None)

    cf = sub.add_parser("create-from-data", help="One-click BMC derived from existing platform data")
    cf.add_argument("--canvas-name", default="Primary Canvas (auto)")
    cf.add_argument("--description", default=None)
    cf.add_argument("--fiscal-year", type=int, default=None)
    cf.add_argument("--tags", nargs="*", default=["auto-generated"])
    cf.add_argument("--created-by", default=None)

    sub.add_parser("list")

    g = sub.add_parser("get")
    g.add_argument("--canvas-id", required=True)

    u = sub.add_parser("update-block")
    u.add_argument("--canvas-id", required=True)
    u.add_argument("--block", required=True, choices=BMC_BLOCKS)
    u.add_argument("--items", default="[]", help="JSON array or object")
    u.add_argument("--updated-by", default=None)

    v = sub.add_parser("version")
    v.add_argument("--canvas-id", required=True)
    v.add_argument("--changes", default=None)
    v.add_argument("--change_reason", default=None)
    v.add_argument("--created-by", default=None)

    lv = sub.add_parser("list-versions")
    lv.add_argument("--canvas-id", required=True)

    s = sub.add_parser("suggest")
    s.add_argument("--location-id", required=True)

    h = sub.add_parser("health")
    h.add_argument("--canvas-id", required=True)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
