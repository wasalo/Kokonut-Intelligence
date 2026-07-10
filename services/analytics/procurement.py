"""Procurement analytics for bulk purchasing cooperative.

Tracks supplier performance, bulk savings, order efficiency,
and cooperative buying patterns.

Usage:
    python3 -m services.analytics --bulk-savings --group-buy-id UUID
    python3 -m services.analytics --supplier-comparison --location-id UUID
    python3 -m services.analytics --procurement-efficiency --location-id UUID
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.procurement")


def compute_bulk_savings(conn, group_buy_id: str) -> Dict[str, Any]:
    """Compute savings from bulk purchasing vs individual buying.

    Compares total cost under group buy with estimated individual cost.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get group buy details
    cur.execute("SELECT * FROM group_buy WHERE id = %s", (group_buy_id,))
    gb = cur.fetchone()
    if not gb:
        cur.close()
        return {"status": "error", "message": "Group buy not found"}

    gb = dict(gb)

    # Get participating orders
    cur.execute("""
        SELECT po.id, po.total_amount, po.discount_pct, po.shipping_cost,
               gbp.committed_quantity
        FROM purchase_order po
        JOIN group_buy_participation gbp ON gbp.order_id = po.id
        WHERE gbp.group_buy_id = %s AND po.status NOT IN ('cancelled')
    """, (group_buy_id,))
    orders = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_actual = sum(float(o.get("total_amount", 0) or 0) for o in orders)
    total_discount = sum(
        float(o.get("total_amount", 0) or 0) * float(o.get("discount_pct", 0) or 0) / 100
        for o in orders
    )
    total_shipping = sum(float(o.get("shipping_cost", 0) or 0) for o in orders)
    total_committed = sum(float(o.get("committed_quantity", 0) or 0) for o in orders)

    # Estimate individual cost (no bulk discount, individual shipping)
    estimated_individual = total_actual + total_discount + (total_shipping * len(orders))
    savings = estimated_individual - total_actual
    savings_pct = (savings / estimated_individual * 100) if estimated_individual > 0 else 0

    return {
        "group_buy_id": group_buy_id,
        "group_buy_name": gb["group_buy_name"],
        "participant_count": len(orders),
        "total_committed_quantity": float(total_committed),
        "total_actual_cost": round(total_actual, 2),
        "total_discount_savings": round(total_discount, 2),
        "total_shipping_savings": round(savings - total_discount, 2),
        "estimated_individual_cost": round(estimated_individual, 2),
        "total_savings": round(savings, 2),
        "savings_pct": round(savings_pct, 2),
        "volume_discount_achieved": gb.get("volume_discount_pct", 0),
    }


def compute_supplier_comparison(conn, location_id: str = None, product_category: str = None) -> List[Dict[str, Any]]:
    """Compare suppliers by quality, reliability, and pricing."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
        SELECT
            sp.id AS supplier_id,
            sp.name AS supplier_name,
            sp.supplier_type,
            sp.quality_rating,
            sp.reliability_score,
            sp.delivery_lead_time_days,
            sp.payment_terms,
            COUNT(DISTINCT po.id) AS order_count,
            COALESCE(SUM(po.total_amount), 0) AS total_spend,
            COALESCE(AVG(po.total_amount), 0) AS avg_order_value,
            COALESCE(AVG(po.discount_pct), 0) AS avg_discount_pct,
            MAX(sqa.overall_score) AS latest_quality_score
        FROM supplier_profile sp
        LEFT JOIN purchase_order po ON po.supplier_id = sp.id AND po.status NOT IN ('cancelled')
        LEFT JOIN LATERAL (
            SELECT overall_score FROM supplier_quality_assessment
            WHERE supplier_id = sp.id ORDER BY assessment_date DESC LIMIT 1
        ) sqa ON TRUE
        WHERE sp.status = 'active'
    """
    params = []

    if location_id:
        query += " AND po.location_id = %s"
        params.append(location_id)
    if product_category:
        query += " AND EXISTS (SELECT 1 FROM purchase_order_item poi JOIN purchase_order po2 ON poi.order_id = po2.id WHERE po2.supplier_id = sp.id AND poi.product_category = %s)"
        params.append(product_category)

    query += " GROUP BY sp.id, sp.name, sp.supplier_type, sp.quality_rating, sp.reliability_score, sp.delivery_lead_time_days, sp.payment_terms ORDER BY sp.quality_rating DESC, sp.reliability_score DESC"

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    return rows


def compute_procurement_efficiency(conn, location_id: str) -> Dict[str, Any]:
    """Compute procurement efficiency metrics for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Order statistics
    cur.execute("""
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status = 'paid') AS completed_orders,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_orders,
            COALESCE(SUM(total_amount), 0) AS total_spend,
            COALESCE(AVG(total_amount), 0) AS avg_order_value,
            COALESCE(AVG(discount_pct), 0) AS avg_discount_pct
        FROM purchase_order
        WHERE location_id = %s
    """, (location_id,))
    orders = dict(cur.fetchone() or {})

    # Order cycle time (days from order to delivery)
    cur.execute("""
        SELECT
            AVG(EXTRACT(EPOCH FROM (actual_delivery - order_date)) / 86400) AS avg_cycle_days,
            COUNT(*) FILTER (WHERE actual_delivery <= expected_delivery) AS on_time_count,
            COUNT(*) FILTER (WHERE actual_delivery > expected_delivery) AS late_count
        FROM purchase_order
        WHERE location_id = %s
        AND actual_delivery IS NOT NULL
    """, (location_id,))
    cycle = dict(cur.fetchone() or {})

    # Group buy participation
    cur.execute("""
        SELECT COUNT(DISTINCT gbp.group_buy_id) AS group_buys_joined
        FROM group_buy_participation gbp
        JOIN group_buy gb ON gb.id = gbp.group_buy_id
        WHERE gbp.location_id = %s
        AND gb.status IN ('open', 'closed', 'ordered', 'delivered')
    """, (location_id,))
    gb = dict(cur.fetchone() or {})

    cur.close()

    total_orders = int(orders.get("total_orders", 0) or 0)
    completed = int(orders.get("completed_orders", 0) or 0)
    on_time = int(cycle.get("on_time_count", 0) or 0)
    delivered = on_time + int(cycle.get("late_count", 0) or 0)

    return {
        "location_id": location_id,
        "total_orders": total_orders,
        "completed_orders": completed,
        "cancelled_orders": int(orders.get("cancelled_orders", 0) or 0),
        "completion_rate_pct": round(completed / total_orders * 100, 1) if total_orders > 0 else 0,
        "total_spend": round(float(orders.get("total_spend", 0) or 0), 2),
        "avg_order_value": round(float(orders.get("avg_order_value", 0) or 0), 2),
        "avg_discount_pct": round(float(orders.get("avg_discount_pct", 0) or 0), 2),
        "avg_cycle_days": round(float(cycle.get("avg_cycle_days", 0) or 0), 1),
        "on_time_delivery_pct": round(on_time / delivered * 100, 1) if delivered > 0 else 0,
        "group_buys_joined": int(gb.get("group_buys_joined", 0) or 0),
    }


def create_group_buy(
    conn,
    organizer_location_id: str,
    group_buy_name: str,
    product_category: str,
    target_quantity: float,
    unit: str,
    volume_discount_threshold: float = None,
    volume_discount_pct: float = None,
    end_date: str = None,
) -> str:
    """Create a new group buy for cooperative purchasing."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO group_buy (
            organizer_location_id, group_buy_name, product_category,
            target_quantity, unit, volume_discount_threshold, volume_discount_pct,
            end_date, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
        RETURNING id
    """, (
        organizer_location_id, group_buy_name, product_category,
        target_quantity, unit, volume_discount_threshold, volume_discount_pct,
        end_date,
    ))
    gb_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created group buy: %s for %s", group_buy_name, product_category)
    return gb_id


def join_group_buy(
    conn,
    group_buy_id: str,
    location_id: str,
    committed_quantity: float,
    unit: str,
) -> str:
    """Join a location to a group buy."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO group_buy_participation (group_buy_id, location_id, committed_quantity, unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (group_buy_id, location_id) DO UPDATE SET
            committed_quantity = EXCLUDED.committed_quantity,
            unit = EXCLUDED.unit
        RETURNING id
    """, (group_buy_id, location_id, committed_quantity, unit))
    participation_id = str(cur.fetchone()[0])

    # Update group buy totals
    cur.execute("""
        UPDATE group_buy SET
            current_quantity = (SELECT COALESCE(SUM(committed_quantity), 0) FROM group_buy_participation WHERE group_buy_id = %s),
            participant_count = (SELECT COUNT(*) FROM group_buy_participation WHERE group_buy_id = %s),
            updated_at = NOW()
        WHERE id = %s
    """, (group_buy_id, group_buy_id, group_buy_id))

    conn.commit()
    cur.close()

    logger.info("Location %s joined group buy %s with %s %s", location_id[:8], group_buy_id[:8], committed_quantity, unit)
    return participation_id
