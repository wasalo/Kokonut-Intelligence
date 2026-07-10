"""Logistics and cold chain analytics.

Tracks shipment efficiency, cold chain compliance, spoilage rates,
and transport cost efficiency.

Usage:
    python3 -m services.analytics --spoilage-rate --location-id UUID
    python3 -m services.analytics --cold-chain-compliance --shipment-id UUID
    python3 -m services.analytics --delivery-timeliness --location-id UUID
    python3 -m services.analytics --transport-cost --location-id UUID
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.logistics")


def compute_spoilage_rate(conn, location_id: str) -> Dict[str, Any]:
    """Compute spoilage rate during transport and storage."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) AS total_shipments,
            COUNT(*) FILTER (WHERE actual_arrival IS NOT NULL) AS delivered_shipments
        FROM shipment
        WHERE location_id = %s
    """, (location_id,))
    shipments = dict(cur.fetchone() or {})

    # Quality degradation: compare quality at departure vs arrival
    cur.execute("""
        SELECT
            COUNT(*) AS total_items,
            COUNT(*) FILTER (WHERE quality_at_departure IS NOT NULL AND quality_at_arrival IS NOT NULL) AS graded_items,
            COUNT(*) FILTER (WHERE quality_at_departure IS NOT NULL AND quality_at_arrival IS NOT NULL
                AND quality_at_departure != quality_at_arrival) AS degraded_items,
            COUNT(*) FILTER (WHERE quality_at_departure IS NOT NULL AND quality_at_arrival IS NOT NULL
                AND quality_at_departure > quality_at_arrival) AS downgraded_items
        FROM shipment_item si
        JOIN shipment s ON si.shipment_id = s.id
        WHERE s.location_id = %s
    """, (location_id,))
    quality = dict(cur.fetchone() or {})

    # Loss events linked to transport
    cur.execute("""
        SELECT COALESCE(SUM(loss_estimated_value), 0) AS transport_loss_value
        FROM harvest_event he
        WHERE he.location_id = %s
        AND he.loss_reason ILIKE '%transport%'
    """, (location_id,))
    loss = dict(cur.fetchone() or {})

    cur.close()

    graded = int(quality.get("graded_items", 0) or 0)
    downgraded = int(quality.get("downgraded_items", 0) or 0)

    return {
        "location_id": location_id,
        "total_shipments": int(shipments.get("total_shipments", 0) or 0),
        "delivered_shipments": int(shipments.get("delivered_shipments", 0) or 0),
        "total_items_graded": graded,
        "quality_downgraded": downgraded,
        "spoilage_rate_pct": round(downgraded / graded * 100, 1) if graded > 0 else 0,
        "transport_loss_value": round(float(loss.get("transport_loss_value", 0) or 0), 2),
    }


def compute_cold_chain_compliance(conn, shipment_id: str = None, location_id: str = None) -> Dict[str, Any]:
    """Compute cold chain compliance percentage."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if shipment_id:
        cur.execute("""
            SELECT
                COUNT(*) AS total_readings,
                COUNT(*) FILTER (WHERE within_range = TRUE) AS compliant,
                COUNT(*) FILTER (WHERE within_range = FALSE) AS out_of_range,
                AVG(temperature_c) AS avg_temp,
                MIN(temperature_c) AS min_temp,
                MAX(temperature_c) AS max_temp
            FROM cold_chain_record
            WHERE shipment_id = %s
        """, (shipment_id,))
    elif location_id:
        cur.execute("""
            SELECT
                COUNT(*) AS total_readings,
                COUNT(*) FILTER (WHERE within_range = TRUE) AS compliant,
                COUNT(*) FILTER (WHERE within_range = FALSE) AS out_of_range,
                AVG(temperature_c) AS avg_temp,
                MIN(temperature_c) AS min_temp,
                MAX(temperature_c) AS max_temp
            FROM cold_chain_record
            WHERE location_id = %s
        """, (location_id,))
    else:
        cur.close()
        return {"status": "error", "message": "Provide shipment_id or location_id"}

    row = dict(cur.fetchone() or {})
    cur.close()

    total = int(row.get("total_readings", 0) or 0)
    compliant = int(row.get("compliant", 0) or 0)

    return {
        "shipment_id": shipment_id,
        "location_id": location_id,
        "total_readings": total,
        "compliant_readings": compliant,
        "out_of_range_readings": int(row.get("out_of_range", 0) or 0),
        "compliance_pct": round(compliant / total * 100, 1) if total > 0 else 0,
        "avg_temperature": round(float(row.get("avg_temp", 0) or 0), 2),
        "min_temperature": round(float(row.get("min_temp", 0) or 0), 2),
        "max_temperature": round(float(row.get("max_temp", 0) or 0), 2),
    }


def compute_delivery_timeliness(conn, location_id: str) -> Dict[str, Any]:
    """Compute on-time delivery rate."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) AS total_delivered,
            COUNT(*) FILTER (WHERE actual_arrival <= estimated_arrival) AS on_time,
            COUNT(*) FILTER (WHERE actual_arrival > estimated_arrival) AS late,
            AVG(EXTRACT(EPOCH FROM (actual_arrival - estimated_arrival)) / 3600) AS avg_delay_hours,
            AVG(EXTRACT(EPOCH FROM (actual_arrival - departure_time)) / 3600) AS avg_duration_hours
        FROM shipment
        WHERE location_id = %s
        AND actual_arrival IS NOT NULL
        AND estimated_arrival IS NOT NULL
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()

    total = int(row.get("total_delivered", 0) or 0)
    on_time = int(row.get("on_time", 0) or 0)

    return {
        "location_id": location_id,
        "total_delivered": total,
        "on_time": on_time,
        "late": int(row.get("late", 0) or 0),
        "on_time_pct": round(on_time / total * 100, 1) if total > 0 else 0,
        "avg_delay_hours": round(float(row.get("avg_delay_hours", 0) or 0), 1),
        "avg_duration_hours": round(float(row.get("avg_duration_hours", 0) or 0), 1),
    }


def compute_transport_cost(conn, location_id: str) -> Dict[str, Any]:
    """Compute transport cost per kg and total transport spend."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) AS total_trips,
            COALESCE(SUM(tl.fuel_cost), 0) AS total_fuel_cost,
            COALESCE(SUM(tl.distance_km), 0) AS total_distance_km,
            COALESCE(SUM(tl.emissions_kg_co2e), 0) AS total_emissions_kg,
            COALESCE(AVG(tl.fuel_liters), 0) AS avg_fuel_per_trip
        FROM transport_log tl
        WHERE tl.location_id = %s
    """, (location_id,))
    transport = dict(cur.fetchone() or {})

    # Total quantity shipped
    cur.execute("""
        SELECT COALESCE(SUM(si.quantity), 0) AS total_quantity
        FROM shipment_item si
        JOIN shipment s ON si.shipment_id = s.id
        WHERE s.location_id = %s
    """, (location_id,))
    quantity = dict(cur.fetchone() or {})

    cur.close()

    total_cost = float(transport.get("total_fuel_cost", 0) or 0)
    total_qty = float(quantity.get("total_quantity", 0) or 0)
    total_distance = float(transport.get("total_distance_km", 0) or 0)
    total_emissions = float(transport.get("total_emissions_kg", 0) or 0)
    trips = int(transport.get("total_trips", 0) or 0)

    return {
        "location_id": location_id,
        "total_trips": trips,
        "total_fuel_cost": round(total_cost, 2),
        "total_distance_km": round(total_distance, 1),
        "total_quantity_shipped": round(total_qty, 2),
        "total_emissions_kg_co2e": round(total_emissions, 4),
        "cost_per_kg": round(total_cost / total_qty, 4) if total_qty > 0 else 0,
        "cost_per_km": round(total_cost / total_distance, 4) if total_distance > 0 else 0,
        "emissions_per_kg": round(total_emissions / total_qty, 6) if total_qty > 0 else 0,
        "avg_fuel_per_trip": round(float(transport.get("avg_fuel_per_trip", 0) or 0), 2),
    }
