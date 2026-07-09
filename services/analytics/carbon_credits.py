"""Carbon credit issuance, adjustment, retirement, and transfer.

Tracks tokenized carbon credits with auto-adjustment when new
measurements arrive.  Credits are representations of verified
sequestration, not independent financial instruments.

Usage:
    python3 -m services.analytics.carbon_credits --issue --location-id UUID --vintage-year 2026 --methodology "IPCC 2006 Tier 2"
    python3 -m services.analytics.carbon_credits --adjust --location-id UUID
    python3 -m services.analytics.carbon_credits --retire --credit-id UUID --tonnes 5.0 --reason voluntary_retirement
    python3 -m services.analytics.carbon_credits --list --location-id UUID
    python3 -m services.analytics.carbon_credits --balance --location-id UUID
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger
from .carbon_balance import compute_carbon_balance

logger = get_logger("analytics.carbon_credits")


def _generate_credit_code(conn, location_id: str, vintage_year: int) -> str:
    """Generate unique credit code: KKNT-{year}-{location_prefix}-{seq}."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM carbon_credit
        WHERE location_id = %s AND vintage_year = %s
    """, (location_id, vintage_year))
    count = cur.fetchone()[0]
    cur.close()

    # Get location prefix (first 8 chars of name, uppercase)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    row = cur.fetchone()
    cur.close()
    prefix = (row["name"][:8].upper().replace(" ", "") if row else "LOC")[:8]

    return f"KKNT-{vintage_year}-{prefix}-{count + 1:04d}"


def _query_climate_impact(conn, location_id: str, vintage_year: int) -> Optional[Dict[str, Any]]:
    """Get climate impact summary for credit issuance."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM climate_impact_summary
        WHERE location_id = %s
        AND EXTRACT(YEAR FROM period_start) <= %s
        AND EXTRACT(YEAR FROM period_end) >= %s
        AND status IN ('verified', 'published')
        ORDER BY period_end DESC
        LIMIT 1
    """, (location_id, vintage_year, vintage_year))
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None


def _get_latest_price(conn, location_id: str) -> Optional[float]:
    """Get latest carbon credit market price."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT price_usd_per_tonne FROM price_observation
        WHERE commodity = 'carbon_credit'
        AND location_id = %s
        ORDER BY observation_date DESC
        LIMIT 1
    """, (location_id,))
    row = cur.fetchone()
    cur.close()
    return float(row["price_usd_per_tonne"]) if row else None


def issue_credit(
    conn,
    location_id: str,
    vintage_year: int,
    methodology: str,
    methodology_version: str = None,
    adjustment_margin_pct: float = 10.0,
    buffer_pool_pct: float = 20.0,
    price_per_tonne_usd: float = 25.0,
) -> Dict[str, Any]:
    """Issue a new carbon credit from verified climate impact data.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        vintage_year: Credit vintage year.
        methodology: Carbon accounting methodology.
        methodology_version: Methodology version string.
        adjustment_margin_pct: Max % adjustment allowed without review.
        buffer_pool_pct: % held in buffer for permanence risk.
        price_per_tonne_usd: Default price per tonne.

    Returns:
        Dict with credit details.
    """
    # Get climate impact summary
    impact = _query_climate_impact(conn, location_id, vintage_year)
    if not impact:
        return {"status": "error", "message": "No verified climate impact summary found"}

    # Compute sequestration from impact data
    sequestration = float(impact.get("total_sequestration_tonnes_co2e", 0) or 0)
    if sequestration <= 0:
        return {"status": "error", "message": "No positive sequestration in climate impact summary"}

    # Apply buffer pool
    issuable = sequestration * (1 - buffer_pool_pct / 100)

    # Generate credit code
    credit_code = _generate_credit_code(conn, location_id, vintage_year)

    # Get market price if available
    market_price = _get_latest_price(conn, location_id)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO carbon_credit (
            location_id, farm_id, credit_code, vintage_year,
            methodology, methodology_version,
            initial_sequestration_tonnes, current_sequestration_tonnes,
            adjustment_margin_pct, buffer_pool_pct, issuable_tonnes,
            price_per_tonne_usd, market_price_per_tonne_usd,
            climate_impact_summary_id, evidence_maturity,
            status, source_system
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', 'carbon_credit_service'
        ) RETURNING id
    """, (
        location_id, impact.get("farm_id"), credit_code, vintage_year,
        methodology, methodology_version,
        sequestration, sequestration,
        adjustment_margin_pct, buffer_pool_pct, issuable,
        price_per_tonne_usd, market_price,
        str(impact["id"]), 6,  # Level 6 from verified climate impact
    ))
    credit_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Issued credit %s for location %s vintage %s", credit_code, location_id[:8], vintage_year)
    return {
        "status": "success",
        "credit_id": credit_id,
        "credit_code": credit_code,
        "sequestration_tonnes": sequestration,
        "issuable_tonnes": issuable,
        "buffer_pool_pct": buffer_pool_pct,
    }


def recompute_sequestration(conn, location_id: str, vintage_year: int) -> float:
    """Recompute sequestration from live verified data."""
    result = compute_carbon_balance(conn, location_id)
    return float(result.get("net_sequestration_tonnes_co2e", 0) or 0)


def adjust_credit(
    conn,
    credit_id: str,
    trigger_source: str,
    trigger_record_id: str = None,
) -> Dict[str, Any]:
    """Auto-adjust a carbon credit based on new measurements.

    If adjustment is within margin -> automatic update.
    If outside margin or reversal -> queue for human review.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM carbon_credit WHERE id = %s", (credit_id,))
    credit = cur.fetchone()
    cur.close()

    if not credit:
        return {"status": "error", "message": "Credit not found"}

    if credit["status"] not in ("verified", "published"):
        return {"status": "error", "message": f"Cannot adjust credit in '{credit['status']}' status"}

    old_sequestration = float(credit["current_sequestration_tonnes"])
    new_sequestration = recompute_sequestration(conn, str(credit["location_id"]), credit["vintage_year"])

    delta_tonnes = new_sequestration - old_sequestration
    delta_pct = (delta_tonnes / old_sequestration * 100) if old_sequestration > 0 else 0
    margin = float(credit["adjustment_margin_pct"])

    within_margin = abs(delta_pct) <= margin
    is_reversal = delta_tonnes < 0

    # Capture measurement snapshot
    snapshot = {"trigger_source": trigger_source, "trigger_record_id": trigger_record_id}

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO credit_adjustment (
            credit_id, location_id, adjustment_type,
            previous_sequestration_tonnes, new_sequestration_tonnes,
            delta_tonnes, delta_pct,
            trigger_source, trigger_record_id, trigger_snapshot,
            within_margin, requires_review, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        RETURNING id
    """, (
        credit_id, str(credit["location_id"]),
        "reversal" if is_reversal else "measurement_update",
        old_sequestration, new_sequestration,
        delta_tonnes, round(delta_pct, 4),
        trigger_source, trigger_record_id, json.dumps(snapshot),
        within_margin, (not within_margin) or is_reversal,
        "verified" if (within_margin and not is_reversal) else "submitted",
    ))
    adjustment_id = str(cur.fetchone()[0])

    if within_margin and not is_reversal:
        # Auto-adjust
        issuable = new_sequestration * (1 - float(credit["buffer_pool_pct"]) / 100)
        cur.execute("""
            UPDATE carbon_credit SET
                current_sequestration_tonnes = %s,
                issuable_tonnes = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (new_sequestration, issuable, credit_id))
        logger.info("Auto-adjusted credit %s: %.2f -> %.2f tonnes (%.1f%%)",
                     credit["credit_code"], old_sequestration, new_sequestration, delta_pct)
    else:
        logger.info("Credit %s adjustment requires review: %.2f -> %.2f tonnes (%.1f%%)",
                     credit["credit_code"], old_sequestration, new_sequestration, delta_pct)

    conn.commit()
    cur.close()

    return {
        "status": "success",
        "adjustment_id": adjustment_id,
        "credit_code": credit["credit_code"],
        "previous_tonnes": old_sequestration,
        "new_tonnes": new_sequestration,
        "delta_tonnes": delta_tonnes,
        "delta_pct": round(delta_pct, 4),
        "within_margin": within_margin,
        "requires_review": (not within_margin) or is_reversal,
        "auto_adjusted": within_margin and not is_reversal,
    }


def retire_credit(
    conn,
    credit_id: str,
    retired_tonnes: float,
    reason: str,
    beneficiary_name: str = None,
    retirement_statement: str = None,
) -> Dict[str, Any]:
    """Permanently retire carbon credits."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM carbon_credit WHERE id = %s", (credit_id,))
    credit = cur.fetchone()
    cur.close()

    if not credit:
        return {"status": "error", "message": "Credit not found"}

    available = float(credit["issuable_tonnes"]) - float(credit["retired_tonnes"])
    if retired_tonnes > available:
        return {"status": "error", "message": f"Only {available:.4f} tonnes available for retirement"}

    price = float(credit["effective_price_per_tonne_usd"])
    value = retired_tonnes * price

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO credit_retirement (
            credit_id, location_id, retirement_reason,
            retired_tonnes, retirement_value_usd,
            beneficiary_name, retirement_statement, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft')
        RETURNING id
    """, (
        credit_id, str(credit["location_id"]), reason,
        retired_tonnes, value,
        beneficiary_name, retirement_statement,
    ))
    retirement_id = str(cur.fetchone()[0])

    # Update credit retired_tonnes
    cur.execute("""
        UPDATE carbon_credit SET
            retired_tonnes = retired_tonnes + %s,
            updated_at = NOW()
        WHERE id = %s
    """, (retired_tonnes, credit_id))

    conn.commit()
    cur.close()

    return {
        "status": "success",
        "retirement_id": retirement_id,
        "credit_code": credit["credit_code"],
        "retired_tonnes": retired_tonnes,
        "value_usd": value,
    }


def list_credits(conn, location_id: str = None, vintage_year: int = None) -> List[Dict[str, Any]]:
    """List carbon credits."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT cc.*, l.name AS location_name
        FROM carbon_credit cc
        JOIN location l ON l.id = cc.location_id
        WHERE 1=1
    """
    params = []
    if location_id:
        query += " AND cc.location_id = %s"
        params.append(location_id)
    if vintage_year:
        query += " AND cc.vintage_year = %s"
        params.append(vintage_year)
    query += " ORDER BY cc.created_at DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def get_balance(conn, location_id: str) -> Dict[str, Any]:
    """Get credit balance summary for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total_credits,
            COALESCE(SUM(issuable_tonnes), 0) AS total_issuable,
            COALESCE(SUM(retired_tonnes), 0) AS total_retired,
            COALESCE(SUM(available_tonnes), 0) AS total_available,
            COALESCE(SUM(total_value_usd), 0) AS total_value,
            COUNT(*) FILTER (WHERE status = 'published') AS published,
            COUNT(*) FILTER (WHERE status = 'retired') AS retired
        FROM carbon_credit
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    row["location_id"] = location_id
    return row


def check_adjustments(conn, location_id: str = None) -> List[Dict[str, Any]]:
    """Check all credits for pending adjustments."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT id, credit_code, location_id, vintage_year,
               current_sequestration_tonnes, adjustment_margin_pct
        FROM carbon_credit
        WHERE status IN ('verified', 'published')
    """
    params = []
    if location_id:
        query += " AND location_id = %s"
        params.append(location_id)
    cur.execute(query, params)
    credits = [dict(r) for r in cur.fetchall()]
    cur.close()

    results = []
    for credit in credits:
        new_seq = recompute_sequestration(conn, str(credit["location_id"]), credit["vintage_year"])
        old_seq = float(credit["current_sequestration_tonnes"])
        delta_pct = abs((new_seq - old_seq) / old_seq * 100) if old_seq > 0 else 0

        if delta_pct > 0.1:  # Only flag if > 0.1% change
            results.append({
                "credit_code": credit["credit_code"],
                "current_tonnes": old_seq,
                "recomputed_tonnes": new_seq,
                "delta_pct": round(delta_pct, 4),
                "needs_adjustment": True,
            })

    return results


if __name__ == "__main__":
    import argparse

    from ..common.db import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
    import psycopg2

    parser = argparse.ArgumentParser(description="Carbon credit management")
    parser.add_argument("--issue", action="store_true", help="Issue a new carbon credit")
    parser.add_argument("--adjust", action="store_true", help="Auto-adjust credits")
    parser.add_argument("--retire", action="store_true", help="Retire carbon credits")
    parser.add_argument("--list", action="store_true", help="List carbon credits")
    parser.add_argument("--balance", action="store_true", help="Show credit balance")
    parser.add_argument("--check-adjustments", action="store_true", help="Check for pending adjustments")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--credit-id", help="Credit UUID")
    parser.add_argument("--vintage-year", type=int, help="Vintage year")
    parser.add_argument("--methodology", default="IPCC 2006 Tier 2")
    parser.add_argument("--tonnes", type=float, help="Tonnes to retire")
    parser.add_argument("--reason", help="Retirement reason")
    parser.add_argument("--beneficiary", help="Beneficiary name")
    parser.add_argument("--statement", help="Retirement statement")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )
    try:
        if args.issue:
            if not args.location_id or not args.vintage_year:
                parser.error("--issue requires --location-id and --vintage-year")
            result = issue_credit(conn, args.location_id, args.vintage_year, args.methodology)
            print(json.dumps(result, indent=2, default=str))
        elif args.adjust:
            if not args.location_id:
                parser.error("--adjust requires --location-id")
            credits = list_credits(conn, location_id=args.location_id)
            results = []
            for c in credits:
                if c["status"] in ("verified", "published"):
                    r = adjust_credit(conn, c["id"], "manual_override")
                    results.append(r)
            print(json.dumps(results, indent=2, default=str))
        elif args.retire:
            if not args.credit_id or not args.tonnes or not args.reason:
                parser.error("--retire requires --credit-id, --tonnes, and --reason")
            result = retire_credit(conn, args.credit_id, args.tonnes, args.reason, args.beneficiary, args.statement)
            print(json.dumps(result, indent=2, default=str))
        elif args.list:
            credits = list_credits(conn, location_id=args.location_id, vintage_year=args.vintage_year)
            print(json.dumps(credits, indent=2, default=str))
        elif args.balance:
            if not args.location_id:
                parser.error("--balance requires --location-id")
            balance = get_balance(conn, args.location_id)
            print(json.dumps(balance, indent=2, default=str))
        elif args.check_adjustments:
            results = check_adjustments(conn, location_id=args.location_id)
            print(json.dumps(results, indent=2, default=str))
        else:
            parser.print_help()
    finally:
        conn.close()
