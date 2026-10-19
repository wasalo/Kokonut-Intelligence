"""Business Model Canvas service.

Stores the 9-building-block Osterwalder/Painer Business Model Canvas
per location or organization, with Value Proposition Canvas support
(customer jobs, pain points, gain creators) and auto-suggestion from
existing platform data.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.cli import print_json
from services.common.database import get_db

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
    _entity(org_id, location_id)
    suggestion = suggest(conn, location_id) if location_id else {"blocks": {b: [] if b != "cost_structure" else {} for b in BMC_BLOCKS}, "generated_from": []}
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


def _suggestion_rows(conn, query: str, params: tuple = ()) -> List[tuple]:
    """Run an optional-source read without poisoning the caller's transaction."""
    savepoint = "bmc_optional_source"
    with conn.cursor() as cur:
        cur.execute(f"SAVEPOINT {savepoint}")
        try:
            cur.execute(query, params)
            rows = cur.fetchall()
        except psycopg2.Error:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            return []
        cur.execute(f"RELEASE SAVEPOINT {savepoint}")
        return rows


def suggest(
    conn, location_id: str,
) -> Dict[str, Any]:
    """Build best-effort suggestions from records tied to this location.

    Global federation/process catalogs are intentionally excluded. Financial
    values retain their source currency, and stakeholder feedback contributes
    only consented public aggregates with at least five identified respondents.
    """
    generated_from: List[str] = []
    blocks: Dict[str, Any] = {b: [] for b in BMC_BLOCKS}
    blocks["cost_structure"] = {}

    partners = _suggestion_rows(
        conn,
        """
        SELECT partner_name, partner_type FROM (
            SELECT c.name AS partner_name, 'cooperative'::TEXT AS partner_type
              FROM cooperative AS c
             WHERE c.location_id = %s AND c.status = 'active'
            UNION
            SELECT supplier.name, 'supplier'::TEXT
              FROM supply_agreement AS agreement
              JOIN supplier_profile AS supplier ON supplier.id = agreement.supplier_id
             WHERE agreement.location_id = %s
               AND agreement.status = 'active'
               AND agreement.valid_from <= CURRENT_DATE
               AND (agreement.valid_until IS NULL OR agreement.valid_until >= CURRENT_DATE)
               AND supplier.status = 'active'
        ) AS scoped_partners
        ORDER BY partner_name, partner_type LIMIT 20
        """,
        (location_id, location_id),
    )
    if partners:
        blocks["key_partners"] = [{"name": row[0], "type": row[1]} for row in partners]
        generated_from.append("location_cooperative/supply_agreement")

    activities = _suggestion_rows(
        conn,
        """
        SELECT activity_type, COUNT(*)::INTEGER AS verified_observations
          FROM farm_activity
         WHERE location_id = %s
           AND status IN ('verified', 'published')
         GROUP BY activity_type
         ORDER BY COUNT(*) DESC, activity_type
         LIMIT 20
        """,
        (location_id,),
    )
    if activities:
        blocks["key_activities"] = [
            {"name": row[0], "verified_observations": row[1]} for row in activities
        ]
        generated_from.append("verified_farm_activity")

    resources = _suggestion_rows(
        conn,
        """
        SELECT resource_name, resource_type FROM (
            SELECT device.name AS resource_name, 'sensor'::TEXT AS resource_type
              FROM sensor_device AS device
             WHERE device.location_id = %s AND device.status = 'active'
            UNION
            SELECT energy.source_name, 'energy'
              FROM energy_source AS energy
             WHERE energy.location_id = %s AND energy.status = 'active'
            UNION
            SELECT asset.name, ('shared_asset:' || asset.asset_type)::TEXT
              FROM shared_asset AS asset
              LEFT JOIN cooperative AS coop ON coop.id = asset.cooperative_id
             WHERE asset.status IN ('available', 'in_use', 'reserved')
               AND (asset.location_id = %s OR coop.location_id = %s)
        ) AS scoped_resources
        ORDER BY resource_name, resource_type LIMIT 20
        """,
        (location_id, location_id, location_id, location_id),
    )
    if resources:
        blocks["key_resources"] = [
            {"name": row[0], "type": row[1]} for row in resources
        ]
        generated_from.append("location_sensor/energy/shared_asset")

    propositions = _suggestion_rows(
        conn,
        """
        SELECT claim_type, claim_category
          FROM impact_claim
         WHERE location_id = %s
           AND status IN ('verified', 'published')
         ORDER BY created_at DESC, id
         LIMIT 10
        """,
        (location_id,),
    )
    if propositions:
        blocks["value_propositions"] = [
            {"type": row[0], "category": row[1]} for row in propositions
        ]
        generated_from.append("verified_impact_claim")

    channels = _suggestion_rows(
        conn,
        """
        SELECT DISTINCT delivery_channel
          FROM content_delivery
         WHERE location_id = %s
         ORDER BY delivery_channel
         LIMIT 10
        """,
        (location_id,),
    )
    if channels:
        blocks["channels"] = [{"name": row[0]} for row in channels]
        generated_from.append("location_content_delivery")

    segments = _suggestion_rows(
        conn,
        """
        SELECT segment_name, segment_type
          FROM buyer_segment
         WHERE location_id = %s
           AND status IN ('verified', 'published')
         ORDER BY segment_name, segment_type
         LIMIT 10
        """,
        (location_id,),
    )
    if segments:
        blocks["customer_segments"] = [
            {"name": row[0], "type": row[1]} for row in segments
        ]
        generated_from.append("verified_buyer_segment")

    streams = _suggestion_rows(
        conn,
        """
        SELECT revenue_type, SUM(amount_usd) AS total_usd
          FROM revenue_event
         WHERE location_id = %s
           AND status IN ('verified', 'published')
           AND amount_usd IS NOT NULL
         GROUP BY revenue_type
         ORDER BY revenue_type
         LIMIT 10
        """,
        (location_id,),
    )
    if streams:
        blocks["revenue_streams"] = [
            {"type": row[0], "total_usd": float(row[1] or 0)} for row in streams
        ]
        generated_from.append("verified_revenue_event_usd")

    costs = _suggestion_rows(
        conn,
        """
        SELECT category, COALESCE(NULLIF(currency, ''), 'UNKNOWN') AS currency,
               SUM(amount) AS total
          FROM expense_event
         WHERE location_id = %s
           AND status IN ('verified', 'published')
         GROUP BY category, COALESCE(NULLIF(currency, ''), 'UNKNOWN')
         ORDER BY category, currency
         LIMIT 40
        """,
        (location_id,),
    )
    if costs:
        currency_costs: Dict[str, Dict[str, float]] = {}
        for category, currency, total in costs:
            currency_costs.setdefault(category, {})[currency] = float(total or 0)
        blocks["cost_structure"] = currency_costs
        generated_from.append("verified_expense_event_by_currency")

    sentiments = _suggestion_rows(
        conn,
        """
        SELECT sentiment, COUNT(DISTINCT party_id)::INTEGER AS respondents
          FROM stakeholder_feedback
         WHERE location_id = %s
           AND status = 'published'
           AND is_public = TRUE
           AND consent_given = TRUE
           AND consent_scope IN ('public_summary', 'public_quote', 'public_full')
           AND party_id IS NOT NULL
         GROUP BY sentiment
        HAVING COUNT(DISTINCT party_id) >= 5
         ORDER BY sentiment
        """,
        (location_id,),
    )
    if sentiments:
        blocks["customer_relationships"] = [
            {"public_feedback_sentiment": {row[0]: row[1] for row in sentiments}}
        ]
        generated_from.append("consented_public_feedback_cohort")

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
        print_json(out)
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
