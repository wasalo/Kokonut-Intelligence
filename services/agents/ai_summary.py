#!/usr/bin/env python3
"""
AI Summary Generator — Agent-generated narratives for locations

Queries recent operational, financial, and environmental data for a location
and generates a structured text summary. Stores results in the ai_summary table
only when --store is passed.

Usage:
    python3 -m services.agents.ai_summary --location-id UUID
    python3 -m services.agents.ai_summary --location-id UUID --summary-type financial
    python3 -m services.agents.ai_summary --location-id UUID --store
    python3 -m services.agents.ai_summary --list
    python3 -m services.agents.ai_summary --verify <id>
"""

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_pg():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


def _check_registry_backed(conn, location_id: str) -> bool:
    """Verify the location has a verified/published farm registry record."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM farm_registry_record fr
            WHERE fr.location_id = %s AND fr.status IN ('verified', 'published')
        )
        """,
        (location_id,),
    )
    result = cur.fetchone()[0]
    cur.close()
    return result


def generate_operations_summary(conn, location_id: str) -> dict:
    """Generate an operations summary from recent activity data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_kg
        FROM harvest_event WHERE location_id = %s
        AND status IN ('verified', 'published')
        AND harvest_date >= CURRENT_DATE - INTERVAL '90 days'
    """, (location_id,))
    harvests = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total_usd
        FROM sales_event WHERE location_id = %s
        AND sale_date >= CURRENT_DATE - INTERVAL '90 days'
        AND status IN ('verified', 'published')
    """, (location_id,))
    sales = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count
        FROM crop_cycle WHERE location_id = %s AND status = 'active'
    """, (location_id,))
    cycles = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count, sensor_type
        FROM sensor_reading WHERE location_id = %s
        AND reading_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY sensor_type ORDER BY count DESC LIMIT 3
    """, (location_id,))
    sensors = [dict(r) for r in cur.fetchall()]

    cur.close()

    lines = [
        f"## Operations Summary (Last 90 Days)",
        f"",
        f"**Harvests:** {harvests['count']} events, {harvests['total_kg']:.1f} kg total",
        f"**Sales:** {sales['count']} transactions, ${sales['total_usd']:,.2f} revenue",
        f"**Active Cycles:** {cycles['count']} crop cycles in progress",
    ]

    if sensors:
        sensor_strs = [f"{s['sensor_type']} ({s['count']} readings)" for s in sensors]
        lines.append(f"**Sensors:** {', '.join(sensor_strs)}")

    return {
        "content": "\n".join(lines),
        "source_tables": ["harvest_event", "sales_event", "crop_cycle", "sensor_reading"],
        "summary_type": "operations",
    }


def generate_financial_summary(conn, location_id: str) -> dict:
    """Generate a financial summary from revenue and expense data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT c.name as crop_name, COALESCE(SUM(se.total_amount), 0) as revenue
        FROM sales_event se
        JOIN crop_cycle cc ON se.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
        GROUP BY c.name ORDER BY revenue DESC
    """, (location_id,))
    revenue_by_crop = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT ec.name as category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        JOIN expense_category ec ON ee.category = ec.name
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ec.name ORDER BY total DESC LIMIT 5
    """, (location_id,))
    expenses = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT COALESCE(SUM(noi), 0) as total_noi,
               COALESCE(AVG(operating_margin_pct), 0) as avg_margin
        FROM noi_snapshot WHERE location_id = %s
    """, (location_id,))
    noi = dict(cur.fetchone())

    cur.close()

    total_revenue = sum(r["revenue"] for r in revenue_by_crop)
    total_expenses = sum(e["total"] for e in expenses)

    lines = [
        f"## Financial Summary",
        f"",
        f"**Total Revenue:** ${total_revenue:,.2f}",
    ]

    if revenue_by_crop:
        lines.append("**Revenue by Crop:**")
        for r in revenue_by_crop:
            lines.append(f"  - {r['crop_name']}: ${r['revenue']:,.2f}")

    lines.append(f"")
    lines.append(f"**Total Expenses:** ${total_expenses:,.2f}")

    if expenses:
        lines.append("**Top Expense Categories:**")
        for e in expenses[:3]:
            lines.append(f"  - {e['category']}: ${e['total']:,.2f}")

    lines.append(f"")
    lines.append(f"**Net Operating Income:** ${noi['total_noi']:,.2f}")
    lines.append(f"**Average Operating Margin:** {noi['avg_margin']:.1f}%")

    return {
        "content": "\n".join(lines),
        "source_tables": ["sales_event", "expense_event", "noi_snapshot", "crop_cycle", "crop", "expense_category"],
        "summary_type": "financial",
    }


def generate_environmental_summary(conn, location_id: str) -> dict:
    """Generate an environmental summary from ecological data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT carbon_tonnes_per_ha, measurement_date
        FROM soil_carbon_measurement
        WHERE location_id = %s ORDER BY measurement_date DESC LIMIT 1
    """, (location_id,))
    carbon = cur.fetchone()

    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as species_count,
               COUNT(*) as total_observations
        FROM species_observation WHERE location_id = %s
    """, (location_id,))
    biodiversity = dict(cur.fetchone())

    cur.execute("""
        SELECT ndvi, observation_date
        FROM remote_sensing_observation
        WHERE location_id = %s AND ndvi IS NOT NULL
        ORDER BY observation_date DESC LIMIT 1
    """, (location_id,))
    ndvi = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(SUM(rainfall_mm), 0) as total_rainfall,
               COALESCE(AVG(temperature_c), 0) as avg_temp
        FROM weather_observation
        WHERE location_id = %s
        AND observation_date >= CURRENT_DATE - INTERVAL '90 days'
    """, (location_id,))
    weather = dict(cur.fetchone())

    cur.close()

    lines = [f"## Environmental Summary", f""]

    if carbon:
        lines.append(f"**Soil Carbon:** {carbon['carbon_tonnes_per_ha']:.2f} tonnes/ha (measured {carbon['measurement_date']})")

    lines.append(f"**Biodiversity:** {biodiversity['species_count']} species observed across {biodiversity['total_observations']} observations")

    if ndvi:
        ndvi_val = float(ndvi['ndvi'])
        ndvi_health = "excellent" if ndvi_val > 0.7 else "good" if ndvi_val > 0.5 else "moderate" if ndvi_val > 0.3 else "poor"
        lines.append(f"**Vegetation Health:** NDVI {ndvi_val:.3f} ({ndvi_health}) — observed {ndvi['observation_date']}")

    lines.append(f"**Rainfall (90 days):** {weather['total_rainfall']:.1f} mm")
    lines.append(f"**Average Temperature:** {weather['avg_temp']:.1f}°C")

    return {
        "content": "\n".join(lines),
        "source_tables": ["soil_carbon_measurement", "species_observation", "remote_sensing_observation", "weather_observation"],
        "summary_type": "environmental",
    }


GENERATORS = {
    "operations": generate_operations_summary,
    "financial": generate_financial_summary,
    "environmental": generate_environmental_summary,
}


def generate_combined(conn, location_id: str) -> dict:
    """Generate a combined summary from all generators."""
    sections = []
    all_sources = []

    for summary_type, gen_func in GENERATORS.items():
        if summary_type == "combined":
            continue
        result = gen_func(conn, location_id)
        sections.append(result["content"])
        all_sources.extend(result["source_tables"])

    return {
        "content": "\n\n".join(sections),
        "source_tables": list(dict.fromkeys(all_sources)),
        "summary_type": "combined",
    }


GENERATORS["combined"] = generate_combined


def store_summary(conn, location_id: str, summary_type: str, content: str,
                  source_tables: list, model_version: str = "rules-v1") -> str:
    """Store AI summary in the database as a draft."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    cur = conn.cursor()
    summary_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, %s, %s, %s, %s, 'draft')
        RETURNING id
        """,
        (summary_id, location_id, summary_type, content, source_tables, model_version),
    )
    returned_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return returned_id


def list_summaries(conn, location_id: str = None):
    """List existing AI summaries."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            "SELECT id, summary_type, status, created_at, LEFT(content, 80) as preview FROM ai_summary WHERE subject_id = %s ORDER BY created_at DESC LIMIT 20",
            (location_id,),
        )
    else:
        cur.execute("SELECT id, summary_type, status, created_at, LEFT(content, 80) as preview FROM ai_summary ORDER BY created_at DESC LIMIT 20")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def run_ai_summary(location_id: str, summary_type: str = "combined", store: bool = False) -> dict[str, Any]:
    """Generate and optionally store an AI summary with safety checks."""
    assert_agent_action_allowed("read", "ai_summary", {"location_id": location_id})
    conn = get_pg()
    try:
        if not _check_registry_backed(conn, location_id):
            raise ValueError(f"Location {location_id} does not have a verified/published farm registry record")
        generator = GENERATORS[summary_type]
        result = generator(conn, location_id)
        output: dict[str, Any] = {
            "summary": {
                "content": result["content"],
                "source_tables": result["source_tables"],
                "summary_type": result["summary_type"],
                "location_id": location_id,
            },
        }
        if store:
            output["ai_summary_id"] = store_summary(
                conn, location_id, result["summary_type"],
                result["content"], result["source_tables"]
            )
    finally:
        conn.close()

    errors = validate_output("ai_summary_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main():
    parser = argparse.ArgumentParser(description="AI Summary Generator")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--summary-type", choices=list(GENERATORS.keys()), default="combined",
                        help="Type of summary to generate (default: combined)")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    parser.add_argument("--list", action="store_true", help="List existing summaries")
    parser.add_argument("--verify", help="Verify a summary by ID (check content hash)")
    args = parser.parse_args()

    conn = get_pg()

    if args.list:
        summaries = list_summaries(conn, args.location_id)
        if not summaries:
            print("No summaries found.")
        else:
            print(f"{'ID':<38} {'Type':<15} {'Status':<12} {'Created':<20} Preview")
            print("-" * 120)
            for s in summaries:
                print(f"{str(s['id']):<38} {s['summary_type']:<15} {s['status']:<12} {str(s['created_at']):<20} {(s['preview'] or '')[:60]}")
        conn.close()
        return

    if args.verify:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM ai_summary WHERE id = %s", (args.verify,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            print(f"Summary not found: {args.verify}")
        else:
            content_hash = hashlib.sha256(row["content"].encode()).hexdigest()
            print(f"ID: {row['id']}")
            print(f"Type: {row['summary_type']}")
            print(f"Status: {row['status']}")
            print(f"Model: {row['model_version']}")
            print(f"Content hash: {content_hash}")
            print(f"Content length: {len(row['content'])} chars")
        return

    if not args.location_id:
        parser.error("--location-id is required (or use --list)")

    conn.close()

    print(f"Generating {args.summary_type} summary for location {args.location_id}...")
    result = run_ai_summary(args.location_id, args.summary_type, store=args.store)

    print(f"Type: {result['summary']['summary_type']}")
    print(f"Sources: {', '.join(result['summary']['source_tables'])}")
    if "ai_summary_id" in result:
        print(f"Summary stored: {result['ai_summary_id']}")
    else:
        print("Summary not stored (use --store to save as draft)")
    print(f"\n--- Preview ---\n{result['summary']['content'][:500]}")


if __name__ == "__main__":
    main()
