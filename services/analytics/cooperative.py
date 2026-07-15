#!/usr/bin/env python3
"""
Digital Cooperative Services

Manages shared assets and collective action for farmer cooperatives.
Supports cooperative creation, member management, shared asset booking,
collective purchasing, and market order coordination.

Usage:
    python -m services.analytics.cooperative create-coop --name "Adelphi Coop" --type marketing --location-id UUID --governance one_member_one_vote
    python -m services.analytics.cooperative add-member --cooperative-id UUID --farmer-id UUID --role member --shares 10
    python -m services.analytics.cooperative summary --cooperative-id UUID
    python -m services.analytics.cooperative list --location-id UUID
    python -m services.analytics.cooperative add-asset --cooperative-id UUID --name "Tractor" --type tractor --daily-rate 50.00
    python -m services.analytics.cooperative book-asset --asset-id UUID --membership-id UUID --start "2026-07-15T08:00" --end "2026-07-20T17:00"
    python -m services.analytics.cooperative asset-utilization --cooperative-id UUID
    python -m services.analytics.cooperative create-purchase --cooperative-id UUID --order-name "Bulk Seeds" --category seeds --target-qty 1000 --unit kg --target-price 2.50
    python -m services.analytics.cooperative add-purchase-participant --purchase-id UUID --membership-id UUID --quantity 100 --commitment 250.00
    python -m services.analytics.cooperative create-market-order --cooperative-id UUID --order-name "Maize Bulk" --crop maize --quantity 5000 --grade A --target-price 350.00
    python -m services.analytics.cooperative add-market-participant --market-order-id UUID --membership-id UUID --quantity 500
    python -m services.analytics.cooperative collective-orders --cooperative-id UUID
    python -m services.analytics.cooperative member-dashboard --farmer-id UUID
"""

import argparse
import json
import uuid
from datetime import date, datetime
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.cooperative")


# ============================================================
# Cooperative Management
# ============================================================

def create_cooperative(
    conn,
    name: str,
    cooperative_type: str,
    location_id: str,
    governance_model: str = "one_member_one_vote",
    description: str = None,
    mission_statement: str = None,
    metadata: dict = None,
) -> dict:
    """Create a new cooperative."""
    cur = conn.cursor()
    coop_id = str(uuid.uuid4())

    try:
        # Look up type_id
        cur.execute(
            "SELECT id FROM cooperative_type WHERE name = %s",
            (cooperative_type,),
        )
        type_row = cur.fetchone()
        if not type_row:
            return {"error": f"Cooperative type '{cooperative_type}' not found. Use: marketing, input_purchase, equipment_sharing, processing"}
        type_id = type_row[0]

        cur.execute(
            """
            INSERT INTO cooperative
                (id, name, type_id, location_id, governance_model,
                 description, mission_statement, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
            RETURNING id, created_at
            """,
            (coop_id, name, type_id, location_id, governance_model,
             description, mission_statement, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Created cooperative %s: %s", coop_id[:8], name)
        return {
            "cooperative_id": coop_id,
            "name": name,
            "type": cooperative_type,
            "location_id": location_id,
            "governance_model": governance_model,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def add_member(
    conn,
    cooperative_id: str,
    farmer_id: str,
    role: str = "member",
    shares: int = 1,
    member_type: str = "farmer",
    metadata: dict = None,
    party_id: str = None,
) -> dict:
    """Add a member to a cooperative."""
    cur = conn.cursor()
    member_id = str(uuid.uuid4())

    try:
        # Check cooperative exists
        cur.execute(
            "SELECT id FROM cooperative WHERE id = %s",
            (cooperative_id,),
        )
        if not cur.fetchone():
            return {"error": "Cooperative not found"}

        # Get location from cooperative
        cur.execute(
            "SELECT location_id FROM cooperative WHERE id = %s",
            (cooperative_id,),
        )
        location_id = cur.fetchone()[0]

        # Check for existing member
        cur.execute(
            """
            SELECT id FROM cooperative_membership
            WHERE cooperative_id = %s AND member_name = %s AND status = 'active'
            """,
            (cooperative_id, farmer_id),
        )
        if cur.fetchone():
            return {"error": "Member already exists in this cooperative"}

        cur.execute(
            """
            INSERT INTO cooperative_membership
                (id, cooperative_id, location_id, member_name, party_id, member_type,
                 role, share_count, metadata, status)
            VALUES (%s, %s, %s, %s, %s::uuid, %s, %s, %s, %s::jsonb, 'active')
            RETURNING id, created_at
            """,
            (member_id, cooperative_id, location_id, farmer_id, party_id, member_type,
             role, shares, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]

        # Update membership count
        cur.execute(
            """
            UPDATE cooperative
            SET membership_count = (
                SELECT COUNT(*) FROM cooperative_membership
                WHERE cooperative_id = %s AND status = 'active'
            )
            WHERE id = %s
            """,
            (cooperative_id, cooperative_id),
        )
        conn.commit()

        logger.info("Added member %s to cooperative %s", farmer_id[:8], cooperative_id[:8])
        return {
            "member_id": member_id,
            "cooperative_id": cooperative_id,
            "farmer_id": farmer_id,
            "role": role,
            "shares": shares,
            "joined_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def get_cooperative_summary(conn, cooperative_id: str) -> dict:
    """Get cooperative summary with members, assets, and orders."""
    cur = conn.cursor()

    try:
        # Cooperative info
        cur.execute(
            """
            SELECT c.id, c.name, ct.name AS type_name, c.location_id,
                   c.governance_model, c.description, c.mission_statement,
                   c.membership_count, c.total_revenue, c.total_assets_value,
                   c.founded_date, c.status, c.created_at
            FROM cooperative c
            JOIN cooperative_type ct ON c.type_id = ct.id
            WHERE c.id = %s
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        coop_row = cur.fetchone()
        if not coop_row:
            return {"error": "Cooperative not found"}
        coop = dict(zip(cols, coop_row))

        # Members
        cur.execute(
            """
            SELECT cm.id, cm.member_name, cm.member_type, cm.role,
                   cm.share_count, cm.join_date, cm.status
            FROM cooperative_membership cm
            WHERE cm.cooperative_id = %s AND cm.status = 'active'
            ORDER BY cm.join_date
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        members = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Shared assets
        cur.execute(
            """
            SELECT sa.id, sa.name, sa.asset_type, sa.daily_rate,
                   sa.status, sa.condition_rating, sa.total_bookings,
                   sa.avg_utilization_pct
            FROM shared_asset sa
            WHERE sa.cooperative_id = %s AND sa.status != 'decommissioned'
            ORDER BY sa.name
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        assets = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Active bookings
        cur.execute(
            """
            SELECT COUNT(*) AS active_bookings
            FROM asset_booking ab
            WHERE ab.cooperative_id = %s
              AND ab.status IN ('confirmed', 'in_progress')
              AND ab.end_time >= NOW()
            """,
            (cooperative_id,),
        )
        bookings_count = cur.fetchone()[0]

        # Collective purchases
        cur.execute(
            """
            SELECT cp.id, cp.order_name, cp.input_category,
                   cp.target_quantity, cp.unit, cp.negotiated_unit_price,
                   cp.participant_count, cp.status
            FROM collective_purchase cp
            WHERE cp.cooperative_id = %s AND cp.status NOT IN ('completed', 'cancelled')
            ORDER BY cp.created_at DESC
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        purchases = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Market orders
        cur.execute(
            """
            SELECT cmo.id, cmo.order_name, cmo.crop_type,
                   cmo.quality_grade, cmo.total_quantity, cmo.unit,
                   cmo.target_price, cmo.status
            FROM collective_market_order cmo
            WHERE cmo.cooperative_id = %s AND cmo.status NOT IN ('completed', 'cancelled')
            ORDER BY cmo.created_at DESC
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        market_orders = [dict(zip(cols, row)) for row in cur.fetchall()]

        return {
            "cooperative_id": cooperative_id,
            "name": coop["name"],
            "type": coop["type_name"],
            "location_id": coop["location_id"],
            "governance_model": coop["governance_model"],
            "description": coop["description"],
            "mission_statement": coop["mission_statement"],
            "status": coop["status"],
            "membership_count": coop["membership_count"],
            "total_revenue": float(coop["total_revenue"]) if coop["total_revenue"] else 0,
            "total_assets_value": float(coop["total_assets_value"]) if coop["total_assets_value"] else 0,
            "founded_date": coop["founded_date"].isoformat() if coop["founded_date"] else None,
            "created_at": coop["created_at"].isoformat() if coop["created_at"] else None,
            "active_members": len(members),
            "members": members,
            "assets_count": len(assets),
            "assets": assets,
            "active_bookings": bookings_count,
            "active_purchases": len(purchases),
            "purchases": purchases,
            "active_market_orders": len(market_orders),
            "market_orders": market_orders,
        }
    finally:
        cur.close()


def list_cooperatives(conn, location_id: str) -> list:
    """List cooperatives for a location."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT c.id, c.name, ct.name AS type_name, c.governance_model,
                   c.membership_count, c.total_revenue, c.status, c.created_at
            FROM cooperative c
            JOIN cooperative_type ct ON c.type_id = ct.id
            WHERE c.location_id = %s AND c.status != 'archived'
            ORDER BY c.name
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()


# ============================================================
# Shared Asset Management
# ============================================================

def add_shared_asset(
    conn,
    cooperative_id: str,
    name: str,
    asset_type: str,
    daily_rate: float,
    description: str = None,
    capacity: str = None,
    capacity_unit: str = None,
    hourly_rate: float = None,
    purchase_price: float = None,
    metadata: dict = None,
) -> dict:
    """Add a shared asset to a cooperative."""
    cur = conn.cursor()
    asset_id = str(uuid.uuid4())

    try:
        # Get location from cooperative
        cur.execute(
            "SELECT location_id FROM cooperative WHERE id = %s",
            (cooperative_id,),
        )
        coop_row = cur.fetchone()
        if not coop_row:
            return {"error": "Cooperative not found"}
        location_id = coop_row[0]

        cur.execute(
            """
            INSERT INTO shared_asset
                (id, cooperative_id, name, asset_type, daily_rate,
                 description, capacity, capacity_unit, hourly_rate,
                 purchase_price, location_id, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'available')
            RETURNING id, created_at
            """,
            (asset_id, cooperative_id, name, asset_type, daily_rate,
             description, capacity, capacity_unit, hourly_rate,
             purchase_price, location_id, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Added asset %s to cooperative %s", name, cooperative_id[:8])
        return {
            "asset_id": asset_id,
            "cooperative_id": cooperative_id,
            "name": name,
            "asset_type": asset_type,
            "daily_rate": daily_rate,
            "capacity": capacity,
            "capacity_unit": capacity_unit,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def book_asset(
    conn,
    asset_id: str,
    membership_id: str,
    start_time: str,
    end_time: str,
    purpose: str = None,
    field_location: str = None,
    metadata: dict = None,
) -> dict:
    """Book a shared asset for a member."""
    cur = conn.cursor()
    booking_id = str(uuid.uuid4())

    try:
        # Check for conflicting bookings
        cur.execute(
            """
            SELECT id FROM asset_booking
            WHERE asset_id = %s AND status IN ('confirmed', 'in_progress')
              AND start_time <= %s AND end_time >= %s
            """,
            (asset_id, end_time, start_time),
        )
        if cur.fetchone():
            return {"error": "Asset already booked for the requested time window"}

        # Get asset details
        cur.execute(
            """
            SELECT daily_rate, hourly_rate, cooperative_id
            FROM shared_asset WHERE id = %s AND status != 'decommissioned'
            """,
            (asset_id,),
        )
        asset_row = cur.fetchone()
        if not asset_row:
            return {"error": "Asset not found or decommissioned"}
        daily_rate = float(asset_row[0]) if asset_row[0] else 0
        hourly_rate = float(asset_row[1]) if asset_row[1] else 0
        cooperative_id = asset_row[2]

        # Verify membership
        cur.execute(
            """
            SELECT id FROM cooperative_membership
            WHERE id = %s AND cooperative_id = %s AND status = 'active'
            """,
            (membership_id, cooperative_id),
        )
        if not cur.fetchone():
            return {"error": "Membership not found or inactive"}

        # Calculate duration and cost
        from datetime import datetime as dt
        st = dt.fromisoformat(start_time)
        et = dt.fromisoformat(end_time)
        duration_hours = (et - st).total_seconds() / 3600
        total_cost = hourly_rate * duration_hours if hourly_rate > 0 else daily_rate * (duration_hours / 24)

        cur.execute(
            """
            INSERT INTO asset_booking
                (id, asset_id, cooperative_id, membership_id,
                 start_time, end_time, duration_hours, purpose,
                 field_location, hourly_rate, total_cost, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'pending')
            RETURNING id, created_at
            """,
            (booking_id, asset_id, cooperative_id, membership_id,
             start_time, end_time, duration_hours, purpose,
             field_location, hourly_rate, total_cost, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Booked asset %s for membership %s", asset_id[:8], membership_id[:8])
        return {
            "booking_id": booking_id,
            "asset_id": asset_id,
            "membership_id": membership_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": round(duration_hours, 2),
            "daily_rate": daily_rate,
            "hourly_rate": hourly_rate,
            "total_cost": round(total_cost, 2),
            "purpose": purpose,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def get_asset_utilization(conn, cooperative_id: str) -> dict:
    """Get asset utilization metrics for a cooperative."""
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT sa.id, sa.name, sa.asset_type, sa.daily_rate,
                   sa.hourly_rate, sa.total_bookings, sa.avg_utilization_pct,
                   sa.condition_rating, sa.status,
                   (SELECT COUNT(*)
                    FROM asset_booking ab
                    WHERE ab.asset_id = sa.id
                      AND ab.status IN ('confirmed', 'in_progress')
                      AND ab.end_time >= NOW()
                   ) AS upcoming_bookings,
                   (SELECT COALESCE(SUM(ab.duration_hours), 0)
                    FROM asset_booking ab
                    WHERE ab.asset_id = sa.id
                      AND ab.status IN ('confirmed', 'in_progress', 'completed')
                      AND ab.start_time >= DATE_TRUNC('month', NOW())
                      AND ab.end_time <= DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
                   ) AS hours_used_this_month
            FROM shared_asset sa
            WHERE sa.cooperative_id = %s AND sa.status != 'decommissioned'
            ORDER BY sa.avg_utilization_pct DESC NULLS LAST
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        assets = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Overall summary
        total_assets = len(assets)
        avg_utilization = (
            sum(float(a["avg_utilization_pct"]) for a in assets if a["avg_utilization_pct"])
            / total_assets if total_assets > 0 else 0
        )
        total_bookings = sum(a["total_bookings"] or 0 for a in assets)

        return {
            "cooperative_id": cooperative_id,
            "total_assets": total_assets,
            "avg_utilization_pct": round(avg_utilization, 1),
            "total_bookings": total_bookings,
            "assets": assets,
        }
    finally:
        cur.close()


# ============================================================
# Collective Purchasing
# ============================================================

def create_collective_purchase(
    conn,
    cooperative_id: str,
    order_name: str,
    input_category: str,
    target_quantity: float,
    unit: str,
    target_price: float,
    description: str = None,
    deadline: str = None,
    metadata: dict = None,
) -> dict:
    """Create a collective purchase order."""
    cur = conn.cursor()
    purchase_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO collective_purchase
                (id, cooperative_id, order_name, description, input_category,
                 target_quantity, unit, estimated_unit_price, expected_delivery,
                 metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'collecting')
            RETURNING id, created_at
            """,
            (purchase_id, cooperative_id, order_name, description, input_category,
             target_quantity, unit, target_price, deadline,
             json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Created collective purchase %s for %s", purchase_id[:8], order_name)
        return {
            "purchase_id": purchase_id,
            "cooperative_id": cooperative_id,
            "order_name": order_name,
            "input_category": input_category,
            "target_quantity": target_quantity,
            "unit": unit,
            "target_price": target_price,
            "deadline": deadline,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def add_purchase_participant(
    conn,
    purchase_id: str,
    membership_id: str,
    quantity: float,
    commitment_amount: float,
    metadata: dict = None,
) -> dict:
    """Add a participant to a collective purchase."""
    cur = conn.cursor()
    participant_id = str(uuid.uuid4())

    try:
        # Check purchase is collecting
        cur.execute(
            "SELECT cooperative_id, status FROM collective_purchase WHERE id = %s",
            (purchase_id,),
        )
        purchase_row = cur.fetchone()
        if not purchase_row:
            return {"error": "Purchase not found"}
        if purchase_row[1] != "collecting":
            return {"error": "Purchase is not accepting new participants"}

        cooperative_id = purchase_row[0]

        # Verify membership
        cur.execute(
            """
            SELECT id FROM cooperative_membership
            WHERE id = %s AND cooperative_id = %s AND status = 'active'
            """,
            (membership_id, cooperative_id),
        )
        if not cur.fetchone():
            return {"error": "Membership not found or inactive"}

        # Check for duplicate
        cur.execute(
            """
            SELECT id FROM collective_purchase_participant
            WHERE purchase_id = %s AND membership_id = %s AND status != 'cancelled'
            """,
            (purchase_id, membership_id),
        )
        if cur.fetchone():
            return {"error": "Member already participating in this purchase"}

        cur.execute(
            """
            INSERT INTO collective_purchase_participant
                (id, purchase_id, membership_id, quantity_requested,
                 total_cost, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'committed')
            RETURNING id, created_at
            """,
            (participant_id, purchase_id, membership_id, quantity,
             commitment_amount, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]

        # Update participant count
        cur.execute(
            """
            UPDATE collective_purchase
            SET participant_count = (
                SELECT COUNT(*) FROM collective_purchase_participant
                WHERE purchase_id = %s AND status != 'cancelled'
            )
            WHERE id = %s
            """,
            (purchase_id, purchase_id),
        )
        conn.commit()

        logger.info("Added participant to purchase %s", purchase_id[:8])
        return {
            "participant_id": participant_id,
            "purchase_id": purchase_id,
            "membership_id": membership_id,
            "quantity": quantity,
            "commitment_amount": commitment_amount,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


# ============================================================
# Collective Market Orders
# ============================================================

def create_market_order(
    conn,
    cooperative_id: str,
    order_name: str,
    crop_type: str,
    quantity: float,
    unit: str,
    target_price: float,
    quality_grade: str = None,
    description: str = None,
    delivery_date: str = None,
    metadata: dict = None,
) -> dict:
    """Create a collective market order."""
    cur = conn.cursor()
    order_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO collective_market_order
                (id, cooperative_id, order_name, description, crop_type,
                 quality_grade, total_quantity, unit, target_price,
                 delivery_date, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'collecting')
            RETURNING id, created_at
            """,
            (order_id, cooperative_id, order_name, description, crop_type,
             quality_grade, quantity, unit, target_price,
             delivery_date, json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Created market order %s for %s", order_id[:8], crop_type)
        return {
            "market_order_id": order_id,
            "cooperative_id": cooperative_id,
            "order_name": order_name,
            "crop_type": crop_type,
            "quantity": quantity,
            "unit": unit,
            "quality_grade": quality_grade,
            "target_price": target_price,
            "delivery_date": delivery_date,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def add_market_participant(
    conn,
    market_order_id: str,
    membership_id: str,
    quantity: float,
    metadata: dict = None,
) -> dict:
    """Add a participant to a collective market order."""
    cur = conn.cursor()
    participant_id = str(uuid.uuid4())

    try:
        # Check order is collecting
        cur.execute(
            "SELECT cooperative_id, status, total_quantity FROM collective_market_order WHERE id = %s",
            (market_order_id,),
        )
        order_row = cur.fetchone()
        if not order_row:
            return {"error": "Market order not found"}
        if order_row[1] != "collecting":
            return {"error": "Market order is not accepting new participants"}

        cooperative_id = order_row[0]

        # Verify membership
        cur.execute(
            """
            SELECT id FROM cooperative_membership
            WHERE id = %s AND cooperative_id = %s AND status = 'active'
            """,
            (membership_id, cooperative_id),
        )
        if not cur.fetchone():
            return {"error": "Membership not found or inactive"}

        # Check for duplicate
        cur.execute(
            """
            SELECT id FROM collective_market_participant
            WHERE market_order_id = %s AND membership_id = %s AND status != 'cancelled'
            """,
            (market_order_id, membership_id),
        )
        if cur.fetchone():
            return {"error": "Member already participating in this market order"}

        # Check quantity does not exceed order total
        cur.execute(
            """
            SELECT COALESCE(SUM(quantity_offered), 0)
            FROM collective_market_participant
            WHERE market_order_id = %s AND status != 'cancelled'
            """,
            (market_order_id,),
        )
        committed = cur.fetchone()[0]
        if committed + quantity > order_row[2]:
            return {"error": "Quantity exceeds remaining order capacity"}

        cur.execute(
            """
            INSERT INTO collective_market_participant
                (id, market_order_id, membership_id, quantity_offered,
                 metadata, status)
            VALUES (%s, %s, %s, %s, %s::jsonb, 'committed')
            RETURNING id, created_at
            """,
            (participant_id, market_order_id, membership_id, quantity,
             json.dumps(metadata or {})),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        logger.info("Added market participant to order %s", market_order_id[:8])
        return {
            "participant_id": participant_id,
            "market_order_id": market_order_id,
            "membership_id": membership_id,
            "quantity": quantity,
            "created_at": created_at.isoformat() if created_at else None,
        }
    finally:
        cur.close()


def get_collective_orders(conn, cooperative_id: str) -> dict:
    """Get active collective orders (purchases and market orders)."""
    cur = conn.cursor()

    try:
        # Collective purchases
        cur.execute(
            """
            SELECT cp.id, cp.order_name, cp.input_category,
                   cp.target_quantity, cp.unit, cp.negotiated_unit_price,
                   cp.participant_count, cp.status, cp.expected_delivery,
                   (SELECT COALESCE(SUM(cpp.quantity_requested), 0)
                    FROM collective_purchase_participant cpp
                    WHERE cpp.purchase_id = cp.id AND cpp.status != 'cancelled') AS committed_quantity,
                   (SELECT COALESCE(SUM(cpp.total_cost), 0)
                    FROM collective_purchase_participant cpp
                    WHERE cpp.purchase_id = cp.id AND cpp.status != 'cancelled') AS committed_amount
            FROM collective_purchase cp
            WHERE cp.cooperative_id = %s AND cp.status NOT IN ('completed', 'cancelled')
            ORDER BY cp.created_at DESC
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        purchases = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Market orders
        cur.execute(
            """
            SELECT cmo.id, cmo.order_name, cmo.crop_type,
                   cmo.quality_grade, cmo.total_quantity, cmo.unit,
                   cmo.target_price, cmo.status, cmo.delivery_date,
                   (SELECT COALESCE(SUM(cmp.quantity_offered), 0)
                    FROM collective_market_participant cmp
                    WHERE cmp.market_order_id = cmo.id AND cmp.status != 'cancelled') AS committed_quantity,
                   (SELECT COUNT(*)
                    FROM collective_market_participant cmp
                    WHERE cmp.market_order_id = cmo.id AND cmp.status != 'cancelled') AS participants_count
            FROM collective_market_order cmo
            WHERE cmo.cooperative_id = %s AND cmo.status NOT IN ('completed', 'cancelled')
            ORDER BY cmo.created_at DESC
            """,
            (cooperative_id,),
        )
        cols = [d[0] for d in cur.description]
        market_orders = [dict(zip(cols, row)) for row in cur.fetchall()]

        return {
            "cooperative_id": cooperative_id,
            "purchases": purchases,
            "market_orders": market_orders,
        }
    finally:
        cur.close()


# ============================================================
# Member Dashboard
# ============================================================

def get_member_dashboard(conn, farmer_id: str) -> dict:
    """Get a farmer's cooperative memberships, bookings, and participation."""
    cur = conn.cursor()

    try:
        # Memberships
        cur.execute(
            """
            SELECT cm.id, cm.cooperative_id, c.name AS cooperative_name,
                   ct.name AS cooperative_type, cm.role, cm.share_count,
                   cm.join_date, cm.status
            FROM cooperative_membership cm
            JOIN cooperative c ON cm.cooperative_id = c.id
            JOIN cooperative_type ct ON c.type_id = ct.id
            WHERE cm.member_name = %s AND cm.status = 'active'
            ORDER BY cm.join_date
            """,
            (farmer_id,),
        )
        cols = [d[0] for d in cur.description]
        memberships = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Get membership IDs for bookings
        member_ids = [m["id"] for m in memberships]

        # Asset bookings
        bookings = []
        if member_ids:
            cur.execute(
                """
                SELECT ab.id, ab.asset_id, sa.name AS asset_name,
                       sa.asset_type, ab.start_time, ab.end_time,
                       ab.purpose, ab.total_cost, ab.status
                FROM asset_booking ab
                JOIN shared_asset sa ON ab.asset_id = sa.id
                WHERE ab.membership_id = ANY(%s)
                ORDER BY ab.start_time DESC
                LIMIT 20
                """,
                (member_ids,),
            )
            cols = [d[0] for d in cur.description]
            bookings = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Purchase participation
        purchases = []
        if member_ids:
            cur.execute(
                """
                SELECT cpp.id, cpp.purchase_id, cp.order_name,
                       cp.input_category, cp.negotiated_unit_price,
                       cp.unit, cpp.quantity_requested, cpp.total_cost,
                       cp.status
                FROM collective_purchase_participant cpp
                JOIN collective_purchase cp ON cpp.purchase_id = cp.id
                WHERE cpp.membership_id = ANY(%s) AND cpp.status != 'cancelled'
                ORDER BY cp.created_at DESC
                LIMIT 20
                """,
                (member_ids,),
            )
            cols = [d[0] for d in cur.description]
            purchases = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Market order participation
        market_participation = []
        if member_ids:
            cur.execute(
                """
                SELECT cmp.id, cmp.market_order_id, cmo.order_name,
                       cmo.crop_type, cmo.quality_grade, cmo.target_price,
                       cmo.unit, cmp.quantity_offered, cmo.status
                FROM collective_market_participant cmp
                JOIN collective_market_order cmo ON cmp.market_order_id = cmo.id
                WHERE cmp.membership_id = ANY(%s) AND cmp.status != 'cancelled'
                ORDER BY cmo.created_at DESC
                LIMIT 20
                """,
                (member_ids,),
            )
            cols = [d[0] for d in cur.description]
            market_participation = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Summary stats
        total_shares = sum(m["share_count"] or 0 for m in memberships)
        active_bookings = sum(1 for b in bookings if b["status"] in ("confirmed", "in_progress"))
        total_booking_cost = sum(float(b["total_cost"]) for b in bookings if b["total_cost"])

        return {
            "farmer_id": farmer_id,
            "cooperatives_count": len(memberships),
            "total_shares": total_shares,
            "active_bookings": active_bookings,
            "total_booking_cost": round(total_booking_cost, 2),
            "memberships": memberships,
            "bookings": bookings,
            "purchase_participations": purchases,
            "market_order_participations": market_participation,
        }
    finally:
        cur.close()


# ============================================================
# CLI Formatting
# ============================================================

def _format_coop(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Cooperative: {r['name']} ({r['type']})\n"
        f"  ID: {r['cooperative_id'][:8]}...\n"
        f"  Governance: {r['governance_model']}\n"
        f"  Location: {r['location_id'][:8]}..."
    )


def _format_member(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Member added: {r['farmer_id'][:8]}... → {r['cooperative_id'][:8]}...\n"
        f"  Role: {r['role']}, Shares: {r['shares']}"
    )


def _format_summary(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    lines = [
        f"Cooperative: {r['name']} ({r['type']}) — {r['membership_count']} members",
        f"  Assets: {r['assets_count']} ({r['active_bookings']} bookings)",
        f"  Revenue: ${r['total_revenue']:,.2f} | Asset Value: ${r['total_assets_value']:,.2f}",
        f"  Active purchases: {r['active_purchases']}",
        f"  Active market orders: {r['active_market_orders']}",
    ]
    return "\n".join(lines)


def _format_list(coops: list) -> str:
    if not coops:
        return "No cooperatives found."
    lines = []
    for c in coops:
        lines.append(
            f"  {c['name']:20s} {c['type_name']:12s} "
            f"members={c['membership_count']} [{c['status']}]"
        )
    return "\n".join(lines)


def _format_asset(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Asset added: {r['name']} ({r['asset_type']})\n"
        f"  ID: {r['asset_id'][:8]}...\n"
        f"  Daily rate: {r['daily_rate']}"
    )


def _format_booking(r: dict) -> str:
    if "error" in r:
        return f"Booking error: {r['error']}"
    return (
        f"Asset booked: {r['asset_id'][:8]}...\n"
        f"  Membership: {r['membership_id'][:8]}...\n"
        f"  Period: {r['start_time']} → {r['end_time']} ({r['duration_hours']}h)\n"
        f"  Total cost: ${r['total_cost']:.2f}"
    )


def _format_utilization(r: dict) -> str:
    lines = [f"Asset Utilization — {r['cooperative_id'][:8]}... ({r['total_assets']} assets, avg={r['avg_utilization_pct']:.1f}%)"]
    for a in r["assets"]:
        util = a["avg_utilization_pct"] or 0
        bar = "█" * int(util / 5)
        lines.append(
            f"  {a['name']:20s} {bar:20s} {util:.1f}% "
            f"(bookings={a['total_bookings']}, upcoming={a['upcoming_bookings']})"
        )
    return "\n".join(lines) if len(lines) > 1 else "No assets."


def _format_purchase(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Collective purchase: {r['order_name']}\n"
        f"  ID: {r['purchase_id'][:8]}...\n"
        f"  Category: {r['input_category']}\n"
        f"  Quantity: {r['target_quantity']} {r['unit']} @ {r['target_price']}"
    )


def _format_participant(r: dict) -> str:
    if "error" in r:
        return f"Participant error: {r['error']}"
    return (
        f"Participant added: {r['membership_id'][:8]}...\n"
        f"  Quantity: {r['quantity']}, Commitment: ${r['commitment_amount']:.2f}"
    )


def _format_market_order(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Market order: {r['order_name']} ({r['crop_type']})\n"
        f"  ID: {r['market_order_id'][:8]}...\n"
        f"  Grade: {r['quality_grade'] or 'N/A'}\n"
        f"  Quantity: {r['quantity']} {r['unit']} @ {r['target_price']}"
    )


def _format_market_participant(r: dict) -> str:
    if "error" in r:
        return f"Participant error: {r['error']}"
    return (
        f"Market participant added: {r['membership_id'][:8]}...\n"
        f"  Quantity: {r['quantity']}"
    )


def _format_orders(r: dict) -> str:
    lines = [f"Collective Orders — {r['cooperative_id'][:8]}..."]
    for p in r["purchases"]:
        lines.append(
            f"  Purchase: {p['order_name']} ({p['input_category']}) "
            f"{p['committed_quantity']}/{p['target_quantity']} {p['unit']} "
            f"({p['participant_count']} participants)"
        )
    for m in r["market_orders"]:
        lines.append(
            f"  Market: {m['order_name']} ({m['crop_type']}) "
            f"{m['committed_quantity']}/{m['total_quantity']} {m['unit']} "
            f"({m['participants_count']} participants)"
        )
    if not r["purchases"] and not r["market_orders"]:
        lines.append("  No active orders.")
    return "\n".join(lines)


def _format_dashboard(r: dict) -> str:
    lines = [
        f"Member Dashboard — {r['farmer_id'][:8]}...",
        f"  Cooperatives: {r['cooperatives_count']}, Shares: {r['total_shares']}",
        f"  Active bookings: {r['active_bookings']}, Total cost: ${r['total_booking_cost']:.2f}",
    ]
    for m in r["memberships"]:
        lines.append(f"  → {m['cooperative_name']} ({m['role']}, {m['share_count']} shares)")
    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Digital cooperative services")
    sub = parser.add_subparsers(dest="command")

    # Create cooperative
    cc = sub.add_parser("create-coop", help="Create cooperative")
    cc.add_argument("--name", required=True)
    cc.add_argument("--type", required=True, help="Type: marketing, input_purchase, equipment_sharing, processing")
    cc.add_argument("--location-id", required=True)
    cc.add_argument("--governance", default="one_member_one_vote",
                    help="Governance model: one_member_one_vote, proportional, board_directors, delegated, hybrid")
    cc.add_argument("--description")
    cc.add_argument("--mission")
    cc.add_argument("--json", action="store_true")

    # Add member
    am = sub.add_parser("add-member", help="Add member")
    am.add_argument("--cooperative-id", required=True)
    am.add_argument("--farmer-id", required=True, help="Farmer name or ID")
    am.add_argument("--role", default="member", help="Role: member, board_member, treasurer, secretary, chairperson, manager")
    am.add_argument("--shares", type=int, default=1)
    am.add_argument("--member-type", default="farmer", help="Type: farmer, associate, youth, women_group")
    am.add_argument("--party-id", help="Canonical stakeholder party UUID")
    am.add_argument("--json", action="store_true")

    # Summary
    sm = sub.add_parser("summary", help="Cooperative summary")
    sm.add_argument("--cooperative-id", required=True)
    sm.add_argument("--json", action="store_true")

    # List
    ls = sub.add_parser("list", help="List cooperatives")
    ls.add_argument("--location-id", required=True)
    ls.add_argument("--json", action="store_true")

    # Add asset
    aa = sub.add_parser("add-asset", help="Add shared asset")
    aa.add_argument("--cooperative-id", required=True)
    aa.add_argument("--name", required=True)
    aa.add_argument("--type", required=True,
                    help="Asset type: tractor, harvester, irrigation_system, storage_facility, processing_equipment, transport_vehicle, other")
    aa.add_argument("--daily-rate", type=float, required=True)
    aa.add_argument("--description")
    aa.add_argument("--capacity")
    aa.add_argument("--capacity-unit")
    aa.add_argument("--hourly-rate", type=float)
    aa.add_argument("--purchase-price", type=float)
    aa.add_argument("--json", action="store_true")

    # Book asset
    ba = sub.add_parser("book-asset", help="Book shared asset")
    ba.add_argument("--asset-id", required=True)
    ba.add_argument("--membership-id", required=True)
    ba.add_argument("--start", required=True, help="Start datetime YYYY-MM-DDTHH:MM")
    ba.add_argument("--end", required=True, help="End datetime YYYY-MM-DDTHH:MM")
    ba.add_argument("--purpose")
    ba.add_argument("--field-location")
    ba.add_argument("--json", action="store_true")

    # Asset utilization
    au = sub.add_parser("asset-utilization", help="Asset utilization")
    au.add_argument("--cooperative-id", required=True)
    au.add_argument("--json", action="store_true")

    # Create purchase
    cp = sub.add_parser("create-purchase", help="Create collective purchase")
    cp.add_argument("--cooperative-id", required=True)
    cp.add_argument("--order-name", required=True)
    cp.add_argument("--category", required=True,
                    help="Category: seeds, fertilizer, pesticide, herbicide, tools, fuel, feed, organic_inputs, other")
    cp.add_argument("--target-qty", type=float, required=True)
    cp.add_argument("--unit", required=True)
    cp.add_argument("--target-price", type=float, required=True)
    cp.add_argument("--description")
    cp.add_argument("--deadline")
    cp.add_argument("--json", action="store_true")

    # Add purchase participant
    app = sub.add_parser("add-purchase-participant", help="Add purchase participant")
    app.add_argument("--purchase-id", required=True)
    app.add_argument("--membership-id", required=True)
    app.add_argument("--quantity", type=float, required=True)
    app.add_argument("--commitment", type=float, required=True)
    app.add_argument("--json", action="store_true")

    # Create market order
    cmo = sub.add_parser("create-market-order", help="Create collective market order")
    cmo.add_argument("--cooperative-id", required=True)
    cmo.add_argument("--order-name", required=True)
    cmo.add_argument("--crop", required=True)
    cmo.add_argument("--quantity", type=float, required=True)
    cmo.add_argument("--unit", default="kg")
    cmo.add_argument("--grade")
    cmo.add_argument("--target-price", type=float, required=True)
    cmo.add_argument("--description")
    cmo.add_argument("--delivery-date")
    cmo.add_argument("--json", action="store_true")

    # Add market participant
    amp = sub.add_parser("add-market-participant", help="Add market order participant")
    amp.add_argument("--market-order-id", required=True)
    amp.add_argument("--membership-id", required=True)
    amp.add_argument("--quantity", type=float, required=True)
    amp.add_argument("--json", action="store_true")

    # Collective orders
    co = sub.add_parser("collective-orders", help="Active collective orders")
    co.add_argument("--cooperative-id", required=True)
    co.add_argument("--json", action="store_true")

    # Member dashboard
    md = sub.add_parser("member-dashboard", help="Member dashboard")
    md.add_argument("--farmer-id", required=True)
    md.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command in (
        "create-coop", "add-member", "summary", "list",
        "add-asset", "book-asset", "asset-utilization",
        "create-purchase", "add-purchase-participant",
        "create-market-order", "add-market-participant",
        "collective-orders", "member-dashboard",
    ):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "create-coop":
            result = create_cooperative(
                db, args.name, args.type, args.location_id,
                governance_model=args.governance, description=args.description,
                mission_statement=args.mission,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_coop(result)
            print(output)

        elif args.command == "add-member":
            result = add_member(
                db, args.cooperative_id, args.farmer_id,
                role=args.role, shares=args.shares, member_type=args.member_type,
                party_id=args.party_id,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_member(result)
            print(output)

        elif args.command == "summary":
            result = get_cooperative_summary(db, args.cooperative_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_summary(result)
            print(output)

        elif args.command == "list":
            result = list_cooperatives(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_list(result)
            print(output)

        elif args.command == "add-asset":
            result = add_shared_asset(
                db, args.cooperative_id, args.name, args.type,
                args.daily_rate, description=args.description,
                capacity=args.capacity, capacity_unit=args.capacity_unit,
                hourly_rate=args.hourly_rate, purchase_price=args.purchase_price,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_asset(result)
            print(output)

        elif args.command == "book-asset":
            result = book_asset(
                db, args.asset_id, args.membership_id,
                args.start, args.end, purpose=args.purpose,
                field_location=args.field_location,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_booking(result)
            print(output)

        elif args.command == "asset-utilization":
            result = get_asset_utilization(db, args.cooperative_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_utilization(result)
            print(output)

        elif args.command == "create-purchase":
            result = create_collective_purchase(
                db, args.cooperative_id, args.order_name, args.category,
                args.target_qty, args.unit, args.target_price,
                description=args.description, deadline=args.deadline,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_purchase(result)
            print(output)

        elif args.command == "add-purchase-participant":
            result = add_purchase_participant(
                db, args.purchase_id, args.membership_id,
                args.quantity, args.commitment,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_participant(result)
            print(output)

        elif args.command == "create-market-order":
            result = create_market_order(
                db, args.cooperative_id, args.order_name, args.crop,
                args.quantity, args.unit, args.target_price,
                quality_grade=args.grade, description=args.description,
                delivery_date=args.delivery_date,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_market_order(result)
            print(output)

        elif args.command == "add-market-participant":
            result = add_market_participant(
                db, args.market_order_id, args.membership_id, args.quantity,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_market_participant(result)
            print(output)

        elif args.command == "collective-orders":
            result = get_collective_orders(db, args.cooperative_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_orders(result)
            print(output)

        elif args.command == "member-dashboard":
            result = get_member_dashboard(db, args.farmer_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_dashboard(result)
            print(output)

    finally:
        db.close()


if __name__ == "__main__":
    main()
