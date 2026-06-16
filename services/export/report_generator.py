#!/usr/bin/env python3
"""
Report Generator — Farm Summary, Crop NOI, Environmental Impact

Generates structured report snapshots with hash verification.
Stores results in the report_snapshot table.

Usage:
    python3 -m services.export.report_generator --type farm_summary --location-id UUID
    python3 -m services.export.report_generator --type crop_noi --location-id UUID
    python3 -m services.export.report_generator --type environmental --location-id UUID
    python3 -m services.export.report_generator --list
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras


from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_pg():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


# ---------------------------------------------------------------------------
# Report Generators
# ---------------------------------------------------------------------------

def generate_farm_summary(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a farm summary report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Location info
    cur.execute("SELECT * FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    if not location:
        raise ValueError(f"Location {location_id} not found")

    # Farms
    cur.execute("SELECT * FROM farm WHERE location_id = %s", (location_id,))
    farms = [dict(r) for r in cur.fetchall()]

    # Plots
    cur.execute("""
        SELECT p.*, f.name as farm_name
        FROM plot p JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s
    """, (location_id,))
    plots = [dict(r) for r in cur.fetchall()]

    # Active crop cycles
    cur.execute("""
        SELECT cc.*, c.name as crop_name, p.name as plot_name
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
    """, (location_id,))
    crop_cycles = [dict(r) for r in cur.fetchall()]

    # Harvest summary
    cur.execute("""
        SELECT
            COUNT(*) as total_harvests,
            COALESCE(SUM(quantity), 0) as total_quantity,
            COALESCE(AVG(quantity), 0) as avg_harvest_size,
            COUNT(DISTINCT crop_cycle_id) as cycles_with_harvest
        FROM harvest_event
        WHERE location_id = %s
        AND (%s::date IS NULL OR harvest_date >= %s::date)
        AND (%s::date IS NULL OR harvest_date <= %s::date)
    """, (location_id, period_start, period_start, period_end, period_end))
    harvest_summary = dict(cur.fetchone())

    # Financial summary
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END), 0) as total_revenue,
            COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as total_expenses,
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END)
                - SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as net_income
        FROM financial_transaction
        WHERE location_id = %s
        AND (%s::date IS NULL OR transaction_date >= %s::date)
        AND (%s::date IS NULL OR transaction_date <= %s::date)
    """, (location_id, period_start, period_start, period_end, period_end))
    financial = dict(cur.fetchone())

    # Expense breakdown
    cur.execute("""
        SELECT ee.category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ee.category ORDER BY total DESC
    """, (location_id,))
    expense_breakdown = [dict(r) for r in cur.fetchall()]

    # Attestation coverage
    cur.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(CASE WHEN status = 'published' THEN 1 END) as attested,
            COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft
        FROM attestation_record
        WHERE subject_type = 'location' AND subject_id = %s
    """, (location_id,))
    attestation = dict(cur.fetchone())

    cur.close()

    # Build report
    def _serialize(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, (bytes, memoryview)):
            return hashlib.sha256(bytes(obj)).hexdigest()[:16]
        return obj

    report = {
        "report_type": "farm_summary",
        "location": {k: _serialize(v) for k, v in dict(location).items() if k != "boundary" and k != "center"},
        "farms": [{k: _serialize(v) for k, v in f.items()} for f in farms],
        "plots": [{k: _serialize(v) for k, v in p.items()} for p in plots],
        "crop_cycles": [{k: _serialize(v) for k, v in cc.items()} for cc in crop_cycles],
        "harvest_summary": harvest_summary,
        "financial_summary": financial,
        "expense_breakdown": expense_breakdown,
        "attestation_coverage": attestation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return report


def generate_crop_noi(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a crop net operating income report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            cc.id as cycle_id,
            cc.cycle_name,
            c.name as crop_name,
            p.name as plot_name,
            cc.status,
            cc.planting_date,
            cc.actual_harvest_date,
            cc.expected_yield,
            cc.actual_yield,
            cc.expected_revenue,
            cc.actual_revenue
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
        ORDER BY cc.planting_date DESC
    """, (location_id,))
    cycles = [dict(r) for r in cur.fetchall()]

    # Get expenses per crop cycle
    noi_data = []
    for cycle in cycles:
        cur.execute("""
            SELECT
                COALESCE(SUM(ca.allocated_amount), 0) as total_allocated_cost
            FROM crop_cost_allocation ca
            WHERE ca.crop_cycle_id = %s
        """, (cycle["cycle_id"],))
        cost = dict(cur.fetchone())

        actual_revenue = float(cycle["actual_revenue"] or 0)
        allocated_cost = float(cost["total_allocated_cost"])
        noi = actual_revenue - allocated_cost

        noi_data.append({
            "cycle_id": str(cycle["cycle_id"]),
            "cycle_name": cycle["cycle_name"],
            "crop_name": cycle["crop_name"],
            "plot_name": cycle["plot_name"],
            "status": cycle["status"],
            "planting_date": cycle["planting_date"].isoformat() if cycle["planting_date"] else None,
            "actual_harvest_date": cycle["actual_harvest_date"].isoformat() if cycle["actual_harvest_date"] else None,
            "expected_yield": float(cycle["expected_yield"] or 0),
            "actual_yield": float(cycle["actual_yield"] or 0),
            "expected_revenue": float(cycle["expected_revenue"] or 0),
            "actual_revenue": actual_revenue,
            "allocated_cost": allocated_cost,
            "crop_noi": noi,
            "operating_margin_pct": (noi / actual_revenue * 100) if actual_revenue > 0 else 0,
        })

    cur.close()

    total_revenue = sum(d["actual_revenue"] for d in noi_data)
    total_cost = sum(d["allocated_cost"] for d in noi_data)
    total_noi = total_revenue - total_cost

    return {
        "report_type": "crop_noi",
        "location_id": location_id,
        "crop_cycles": noi_data,
        "summary": {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_noi": total_noi,
            "overall_margin_pct": (total_noi / total_revenue * 100) if total_revenue > 0 else 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_environmental(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate an environmental impact report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Soil carbon measurements
    cur.execute("""
        SELECT measurement_date, carbon_tonnes_per_ha, measurement_method, depth_cm
        FROM soil_carbon_measurement
        WHERE location_id = %s
        ORDER BY measurement_date
    """, (location_id,))
    soil_carbon = [dict(r) for r in cur.fetchall()]

    # Species observations
    cur.execute("""
        SELECT observation_date, count, habitat_type, notes
        FROM species_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    species = [dict(r) for r in cur.fetchall()]

    # Remote sensing
    cur.execute("""
        SELECT observation_date, ndvi, ndre, cloud_cover_pct
        FROM remote_sensing_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    remote_sensing = [dict(r) for r in cur.fetchall()]

    # Loss events (environmental)
    cur.execute("""
        SELECT loss_date, loss_type, quantity, unit, cause
        FROM loss_event
        WHERE location_id = %s
        ORDER BY loss_date
    """, (location_id,))
    losses = [dict(r) for r in cur.fetchall()]

    cur.close()

    def _serialize(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return obj

    return {
        "report_type": "environmental",
        "location_id": location_id,
        "soil_carbon": [{k: _serialize(v) for k, v in r.items()} for r in soil_carbon],
        "species_observations": [{k: _serialize(v) for k, v in r.items()} for r in species],
        "remote_sensing": [{k: _serialize(v) for k, v in r.items()} for r in remote_sensing],
        "loss_events": [{k: _serialize(v) for k, v in r.items()} for r in losses],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_revenue_multiplier(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a revenue multiplier opportunity map report."""
    from dataclasses import asdict
    from ..revenue_multiplier.analyzer import analyze_location

    result = analyze_location(location_id)
    return {
        "report_type": "revenue_multiplier",
        "location_id": location_id,
        "location_name": result.location_name,
        "overall_score": result.overall_score,
        "total_opportunity_usd": result.total_opportunity_usd,
        "dimensions": [asdict(d) for d in result.dimensions],
        "generated_at": result.generated_at,
    }


# ---------------------------------------------------------------------------
# Snapshot storage
# ---------------------------------------------------------------------------

REPORT_GENERATORS = {
    "farm_summary": generate_farm_summary,
    "crop_noi": generate_crop_noi,
    "environmental": generate_environmental,
    "revenue_multiplier": generate_revenue_multiplier,
}


def compute_hash(data: dict) -> str:
    """Compute SHA-256 hash of report data for reproducibility."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def store_snapshot(conn, report_data: dict, location_id: str = None, period_start: str = None, period_end: str = None) -> str:
    """Store report snapshot in the database."""
    snapshot_hash = compute_hash(report_data)
    report_type = report_data.get("report_type", "unknown")

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO report_snapshot (report_name, report_type, location_id, period_start, period_end, report_data, snapshot_hash, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'published')
        RETURNING id
        """,
        (
            f"{report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            report_type,
            location_id,
            period_start,
            period_end,
            json.dumps(report_data, default=str),
            snapshot_hash,
        ),
    )
    snapshot_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return snapshot_id


def list_snapshots(conn, location_id: str = None):
    """List existing report snapshots."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            "SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot WHERE location_id = %s ORDER BY created_at DESC LIMIT 20",
            (location_id,),
        )
    else:
        cur.execute("SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot ORDER BY created_at DESC LIMIT 20")
    snapshots = [dict(r) for r in cur.fetchall()]
    cur.close()
    return snapshots


def _verify_snapshot(conn, snapshot_id_or_hash: str) -> None:
    """Verify a snapshot's hash integrity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT id, report_name, report_type, report_data, snapshot_hash, status FROM report_snapshot WHERE id = %s OR snapshot_hash = %s",
        (snapshot_id_or_hash, snapshot_id_or_hash),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        print(f"Snapshot not found: {snapshot_id_or_hash}")
        return

    stored_hash = row["snapshot_hash"]
    report_data = row["report_data"]

    recomputed = compute_hash(report_data)

    print(f"Snapshot:   {row['id']}")
    print(f"Report:     {row['report_name']} ({row['report_type']})")
    print(f"Status:     {row['status']}")
    print(f"Stored:     {stored_hash}")
    print(f"Recomputed: {recomputed}")

    if stored_hash == recomputed:
        print("Result:     PASS -- hash matches, report is intact")
    else:
        print("Result:     FAIL -- hash mismatch, report may have been tampered with")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Kokonut report snapshots")
    parser.add_argument("--type", choices=list(REPORT_GENERATORS.keys()), help="Report type to generate")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--period-start", help="Report period start (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Report period end (YYYY-MM-DD)")
    parser.add_argument("--list", action="store_true", help="List existing snapshots")
    parser.add_argument("--verify", help="Verify a snapshot by hash")
    args = parser.parse_args()

    if not args.list:
        if not args.type:
            parser.error("--type is required (or use --list)")

        if not args.location_id:
            parser.error("--location-id is required")

    conn = get_pg()

    if args.list:
        snapshots = list_snapshots(conn, args.location_id)
        if not snapshots:
            print("No snapshots found.")
        else:
            print(f"{'ID':<38} {'Type':<20} {'Status':<12} {'Created':<20} Hash")
            print("-" * 120)
            for s in snapshots:
                print(f"{str(s['id']):<38} {s['report_type']:<20} {s['status']:<12} {str(s['created_at']):<20} {s['snapshot_hash'][:16]}")
        conn.close()
        return

    if args.verify:
        _verify_snapshot(conn, args.verify)
        conn.close()
        return

    print(f"Generating {args.type} report for location {args.location_id}...")

    generator = REPORT_GENERATORS[args.type]
    report_data = generator(conn, args.location_id, args.period_start, args.period_end)

    snapshot_id = store_snapshot(conn, report_data, args.location_id, args.period_start, args.period_end)
    snapshot_hash = compute_hash(report_data)

    print(f"Snapshot stored: {snapshot_id}")
    print(f"Hash: {snapshot_hash}")
    print(f"Report type: {args.type}")

    conn.close()


if __name__ == "__main__":
    main()
