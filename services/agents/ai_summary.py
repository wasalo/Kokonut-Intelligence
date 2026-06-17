#!/usr/bin/env python3
"""
AI Summary Generator — Agent-generated narratives for locations

Queries recent operational, financial, and environmental data for a location
and generates a structured text summary. Stores results in the ai_summary table.

Usage:
    python3 -m services.agents.ai_summary --location-id UUID
    python3 -m services.agents.ai_summary --location-id UUID --summary-type financial
    python3 -m services.agents.ai_summary --list
    python3 -m services.agents.ai_summary --verify <id>
"""

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


def get_pg():
    from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


def generate_operations_summary(conn, location_id: str) -> dict:
    """Generate an operations summary from recent activity data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Recent harvests
    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_kg
        FROM harvest_event WHERE location_id = %s
        AND status IN ('verified', 'published')
        AND harvest_date >= CURRENT_DATE - INTERVAL '90 days'
    """, (location_id,))
    harvests = dict(cur.fetchone())

    # Recent sales
    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total_usd
        FROM sales_event WHERE location_id = %s
        AND sale_date >= CURRENT_DATE - INTERVAL '90 days'
        AND status IN ('verified', 'published')
    """, (location_id,))
    sales = dict(cur.fetchone())

    # Active crop cycles
    cur.execute("""
        SELECT COUNT(*) as count
        FROM crop_cycle WHERE location_id = %s AND status = 'active'
    """, (location_id,))
    cycles = dict(cur.fetchone())

    # Sensor readings
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

    # Revenue by crop
    cur.execute("""
        SELECT c.name as crop_name, COALESCE(SUM(se.total_amount), 0) as revenue
        FROM sales_event se
        JOIN crop_cycle cc ON se.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
        GROUP BY c.name ORDER BY revenue DESC
    """, (location_id,))
    revenue_by_crop = [dict(r) for r in cur.fetchall()]

    # Expenses by category
    cur.execute("""
        SELECT ec.name as category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        JOIN expense_category ec ON ee.category = ec.name
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ec.name ORDER BY total DESC LIMIT 5
    """, (location_id,))
    expenses = [dict(r) for r in cur.fetchall()]

    # NOI snapshot
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

    # Soil carbon
    cur.execute("""
        SELECT carbon_tonnes_per_ha, measurement_date
        FROM soil_carbon_measurement
        WHERE location_id = %s ORDER BY measurement_date DESC LIMIT 1
    """, (location_id,))
    carbon = cur.fetchone()

    # Species count
    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as species_count,
               COUNT(*) as total_observations
        FROM species_observation WHERE location_id = %s
    """, (location_id,))
    biodiversity = dict(cur.fetchone())

    # Latest NDVI
    cur.execute("""
        SELECT ndvi, observation_date
        FROM remote_sensing_observation
        WHERE location_id = %s AND ndvi IS NOT NULL
        ORDER BY observation_date DESC LIMIT 1
    """, (location_id,))
    ndvi = cur.fetchone()

    # Weather summary
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
        "source_tables": list(dict.fromkeys(all_sources)),  # deduplicate, preserve order
        "summary_type": "combined",
    }


GENERATORS["combined"] = generate_combined


def store_summary(conn, location_id: str, summary_type: str, content: str,
                  source_tables: list, model_version: str = "rules-v1") -> str:
    """Store AI summary in the database."""
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


def main():
    parser = argparse.ArgumentParser(description="AI Summary Generator")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--summary-type", choices=list(GENERATORS.keys()), default="combined",
                        help="Type of summary to generate (default: combined)")
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
        conn.close()
        return

    if not args.location_id:
        parser.error("--location-id is required (or use --list)")

    print(f"Generating {args.summary_type} summary for location {args.location_id}...")

    generator = GENERATORS[args.summary_type]
    result = generator(conn, args.location_id)

    summary_id = store_summary(
        conn, args.location_id, result["summary_type"],
        result["content"], result["source_tables"]
    )

    print(f"Summary stored: {summary_id}")
    print(f"Type: {result['summary_type']}")
    print(f"Sources: {', '.join(result['source_tables'])}")
    print(f"\n--- Preview ---\n{result['content'][:500]}")

    conn.close()


if __name__ == "__main__":
    main()
