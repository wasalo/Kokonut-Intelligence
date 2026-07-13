#!/usr/bin/env python3
"""
Digital Marketplace for Agricultural Produce

Manages produce listings, buyer profiles, price observations, orders,
logistics tracking, price alerts, and AI-assisted listing evaluation.

Usage:
    python -m services.analytics.marketplace create-listing --location-id UUID --crop maize --quantity 500 --unit kg --price 0.50 --grade A
    python -m services.analytics.marketplace list-active --location-id UUID --crop maize
    python -m services.analytics.marketplace record-price --crop maize --market "Adelphi Coop" --price 0.55 --grade A
    python -m services.analytics.marketplace price-trends --crop maize --days 30
    python -m services.analytics.marketplace create-order --listing-id UUID --buyer-id UUID --quantity 200
    python -m services.analytics.marketplace market-overview --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.marketplace")


# ============================================================
# Create Listing
# ============================================================

def create_listing(
    conn,
    location_id: str,
    crop_name: str,
    quantity: float,
    unit: str = "kg",
    price_per_unit: float = None,
    quality_grade: str = None,
    harvest_date: date = None,
    description: str = None,
    images: list = None,
    metadata: dict = None,
) -> dict:
    """Create a produce listing on the marketplace."""
    cur = conn.cursor()
    listing_id = str(uuid.uuid4())

    harvest_date = harvest_date or date.today()

    cur.execute(
        """
        INSERT INTO marketplace_listing
            (id, location_id, crop_name, quantity, unit, price_per_unit,
             quality_grade, harvest_date, description, images, status,
             metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                'active', %s::jsonb, %s)
        RETURNING id
        """,
        (
            listing_id, location_id, crop_name, quantity, unit,
            price_per_unit, quality_grade, harvest_date,
            description, json.dumps(images or []),
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created listing %s for %s %s %s", listing_id, quantity, unit, crop_name)

    return {
        "listing_id": listing_id,
        "location_id": location_id,
        "crop_name": crop_name,
        "quantity": quantity,
        "unit": unit,
        "price_per_unit": price_per_unit,
        "quality_grade": quality_grade,
        "harvest_date": harvest_date.isoformat(),
        "status": "active",
    }


# ============================================================
# Update Listing
# ============================================================

def update_listing(
    conn,
    listing_id: str,
    updates: dict,
) -> dict:
    """Update listing status, price, or other fields."""
    cur = conn.cursor()

    allowed_fields = {
        "status", "price_per_unit", "quantity", "quality_grade",
        "description", "images", "metadata",
    }
    set_clauses = []
    params = []
    for key, value in updates.items():
        if key not in allowed_fields:
            continue
        if key in ("images", "metadata"):
            set_clauses.append(f"{key} = %s::jsonb")
            params.append(json.dumps(value))
        else:
            set_clauses.append(f"{key} = %s")
            params.append(value)

    if not set_clauses:
        cur.close()
        return {"error": "no valid fields to update"}

    set_clauses.append("updated_at = %s")
    params.append(datetime.now(timezone.utc))
    params.append(listing_id)

    cur.execute(
        f"UPDATE marketplace_listing SET {', '.join(set_clauses)} WHERE id = %s RETURNING id",
        tuple(params),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"error": f"listing {listing_id} not found"}

    logger.info("Updated listing %s", listing_id)
    return {"listing_id": listing_id, "updated_fields": list(updates.keys())}


# ============================================================
# Get Listing
# ============================================================

def get_listing(conn, listing_id: str) -> dict:
    """Get listing details."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, location_id, crop_name, quantity, unit, price_per_unit,
               quality_grade, harvest_date, description, images, status,
               metadata, created_at, updated_at
        FROM marketplace_listing
        WHERE id = %s
        """,
        (listing_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": f"listing {listing_id} not found"}

    result = dict(zip(cols, row))
    result["harvest_date"] = result["harvest_date"].isoformat() if result["harvest_date"] else None
    result["created_at"] = result["created_at"].isoformat() if result["created_at"] else None
    result["updated_at"] = result["updated_at"].isoformat() if result["updated_at"] else None
    return result


# ============================================================
# List Active Listings
# ============================================================

def list_active_listings(
    conn,
    location_id: str = None,
    crop_name: str = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List active marketplace listings with optional filters."""
    cur = conn.cursor()

    where = "status = 'active'"
    params = []
    if location_id:
        where += " AND location_id = %s"
        params.append(location_id)
    if crop_name:
        where += " AND crop_name = %s"
        params.append(crop_name)

    cur.execute(
        f"""
        SELECT id, location_id, crop_name, quantity, unit, price_per_unit,
               quality_grade, harvest_date, created_at
        FROM marketplace_listing
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    for r in rows:
        r["harvest_date"] = r["harvest_date"].isoformat() if r["harvest_date"] else None
        r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None

    cur.execute(
        f"SELECT COUNT(*) FROM marketplace_listing WHERE {where}",
        tuple(params),
    )
    total = cur.fetchone()[0]
    cur.close()

    return {
        "listings": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ============================================================
# Create Buyer Profile
# ============================================================

def create_buyer_profile(
    conn,
    name: str,
    buyer_type: str = "individual",
    location: str = None,
    preferences: dict = None,
    contact_info: dict = None,
    metadata: dict = None,
) -> dict:
    """Register a buyer on the marketplace."""
    cur = conn.cursor()
    buyer_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO marketplace_buyer
            (id, name, buyer_type, location, preferences,
             contact_info, metadata, status, created_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'active', %s)
        RETURNING id
        """,
        (
            buyer_id, name, buyer_type, location,
            json.dumps(preferences or {}),
            json.dumps(contact_info or {}),
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created buyer profile %s (%s)", buyer_id, name)

    return {
        "buyer_id": buyer_id,
        "name": name,
        "buyer_type": buyer_type,
        "location": location,
        "status": "active",
    }


# ============================================================
# Record Price Observation
# ============================================================

def record_price(
    conn,
    crop_name: str,
    market_name: str,
    price: float,
    quality_grade: str = None,
    unit: str = "kg",
    currency: str = "USD",
    source: str = "manual",
    metadata: dict = None,
) -> dict:
    """Record a price observation from a market."""
    cur = conn.cursor()
    price_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO marketplace_price_observation
            (id, crop_name, market_name, price, quality_grade,
             unit, currency, source, metadata, observed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            price_id, crop_name, market_name, price, quality_grade,
            unit, currency, source,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded price %s %s/%s at %s", price, currency, unit, market_name)

    return {
        "price_id": price_id,
        "crop_name": crop_name,
        "market_name": market_name,
        "price": price,
        "currency": currency,
        "unit": unit,
        "quality_grade": quality_grade,
    }


# ============================================================
# Get Price Trends
# ============================================================

def get_price_trends(
    conn,
    crop_name: str,
    days: int = 30,
) -> dict:
    """Get price history and trend analysis for a crop."""
    cur = conn.cursor()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    cur.execute(
        """
        SELECT price, quality_grade, market_name, observed_at
        FROM marketplace_price_observation
        WHERE crop_name = %s AND observed_at >= %s
        ORDER BY observed_at
        """,
        (crop_name, cutoff),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    for r in rows:
        r["observed_at"] = r["observed_at"].isoformat() if r["observed_at"] else None

    cur.close()

    if not rows:
        return {
            "crop_name": crop_name,
            "days": days,
            "data_points": 0,
            "trend": "no_data",
        }

    prices = [float(r["price"]) for r in rows]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    # Simple trend: compare first half to second half
    mid = len(prices) // 2
    if mid > 0:
        first_half_avg = sum(prices[:mid]) / mid
        second_half_avg = sum(prices[mid:]) / len(prices[mid:])
        change_pct = (second_half_avg - first_half_avg) / max(first_half_avg, 0.01) * 100
        if abs(change_pct) < 2:
            trend = "stable"
        elif change_pct > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
    else:
        change_pct = 0
        trend = "insufficient_data"

    return {
        "crop_name": crop_name,
        "days": days,
        "data_points": len(prices),
        "avg_price": round(avg_price, 4),
        "min_price": round(min_price, 4),
        "max_price": round(max_price, 4),
        "latest_price": round(prices[-1], 4),
        "trend": trend,
        "change_pct": round(change_pct, 1),
        "observations": rows,
    }


# ============================================================
# Create Order
# ============================================================

def create_order(
    conn,
    listing_id: str,
    buyer_id: str,
    quantity: float,
    offered_price: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Create a buy order for a listing."""
    cur = conn.cursor()
    order_id = str(uuid.uuid4())

    # Fetch listing price if not offered
    if offered_price is None:
        cur.execute(
            "SELECT price_per_unit FROM marketplace_listing WHERE id = %s",
            (listing_id,),
        )
        row = cur.fetchone()
        offered_price = float(row[0]) if row and row[0] else None

    total_amount = round(offered_price * quantity, 2) if offered_price else None

    cur.execute(
        """
        INSERT INTO marketplace_order
            (id, listing_id, buyer_id, quantity, offered_price,
             total_amount, notes, metadata, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'pending', %s)
        RETURNING id
        """,
        (
            order_id, listing_id, buyer_id, quantity, offered_price,
            total_amount, notes,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created order %s for listing %s", order_id, listing_id)

    return {
        "order_id": order_id,
        "listing_id": listing_id,
        "buyer_id": buyer_id,
        "quantity": quantity,
        "offered_price": offered_price,
        "total_amount": total_amount,
        "status": "pending",
    }


# ============================================================
# Update Order Status
# ============================================================

def update_order_status(
    conn,
    order_id: str,
    status: str,
    notes: str = None,
) -> dict:
    """Update order status (pending, confirmed, shipped, delivered, cancelled)."""
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE marketplace_order
        SET status = %s, notes = COALESCE(%s, notes), updated_at = %s
        WHERE id = %s
        RETURNING id
        """,
        (status, notes, datetime.now(timezone.utc), order_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"error": f"order {order_id} not found"}

    logger.info("Order %s status updated to %s", order_id, status)
    return {"order_id": order_id, "status": status}


# ============================================================
# Track Shipment
# ============================================================

def track_shipment(
    conn,
    order_id: str,
    location: str = None,
    temperature: float = None,
    humidity: float = None,
    estimated_arrival: datetime = None,
    carrier: str = None,
    tracking_number: str = None,
    metadata: dict = None,
) -> dict:
    """Update logistics tracking for an order shipment."""
    cur = conn.cursor()
    tracking_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO marketplace_shipment_tracking
            (id, order_id, location, temperature, humidity,
             estimated_arrival, carrier, tracking_number,
             metadata, tracked_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            tracking_id, order_id, location, temperature, humidity,
            estimated_arrival, carrier, tracking_number,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Shipment tracked for order %s at %s", order_id, location)

    return {
        "tracking_id": tracking_id,
        "order_id": order_id,
        "location": location,
        "temperature": temperature,
        "humidity": humidity,
        "carrier": carrier,
        "tracking_number": tracking_number,
    }


# ============================================================
# Get Market Overview
# ============================================================

def get_market_overview(conn, location_id: str) -> dict:
    """Get aggregated market data for a location."""
    cur = conn.cursor()

    # Active listings count
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(quantity), 0)
        FROM marketplace_listing
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    listing_row = cur.fetchone()
    active_listings = int(listing_row[0])
    total_quantity = float(listing_row[1])

    # Listings by crop
    cur.execute(
        """
        SELECT crop_name, COUNT(*) AS count, SUM(quantity) AS total_qty,
               AVG(price_per_unit) AS avg_price
        FROM marketplace_listing
        WHERE location_id = %s AND status = 'active'
        GROUP BY crop_name
        ORDER BY total_qty DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    crop_listings = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Recent prices
    cur.execute(
        """
        SELECT crop_name, AVG(price) AS avg_price, MIN(price) AS min_price,
               MAX(price) AS max_price, COUNT(*) AS observations
        FROM marketplace_price_observation
        WHERE observed_at >= %s
        GROUP BY crop_name
        ORDER BY observations DESC
        """,
        (datetime.now(timezone.utc) - timedelta(days=30),),
    )
    cols = [d[0] for d in cur.description]
    recent_prices = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Order status summary
    cur.execute(
        """
        SELECT o.status, COUNT(*) AS count
        FROM marketplace_order o
        JOIN marketplace_listing l ON o.listing_id = l.id
        WHERE l.location_id = %s
        GROUP BY o.status
        """,
        (location_id,),
    )
    order_statuses = {row[0]: int(row[1]) for row in cur.fetchall()}

    cur.close()

    return {
        "location_id": location_id,
        "active_listings": active_listings,
        "total_quantity_listed": total_quantity,
        "listings_by_crop": crop_listings,
        "recent_prices_30d": recent_prices,
        "order_status_summary": order_statuses,
    }


# ============================================================
# Create Price Alert
# ============================================================

def create_price_alert(
    conn,
    location_id: str,
    crop_name: str,
    threshold: float,
    direction: str = "above",
    currency: str = "USD",
    unit: str = "kg",
    notify_email: str = None,
    metadata: dict = None,
) -> dict:
    """Create a price alert for a crop."""
    cur = conn.cursor()
    alert_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO marketplace_price_alert
            (id, location_id, crop_name, threshold, direction,
             currency, unit, notify_email, metadata, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active', %s)
        RETURNING id
        """,
        (
            alert_id, location_id, crop_name, threshold, direction,
            currency, unit, notify_email,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created price alert %s for %s (%s %s %s)", alert_id, crop_name, direction, threshold, currency)

    return {
        "alert_id": alert_id,
        "location_id": location_id,
        "crop_name": crop_name,
        "threshold": threshold,
        "direction": direction,
        "currency": currency,
        "unit": unit,
        "status": "active",
    }


# ============================================================
# Evaluate Listing (AI-assisted)
# ============================================================

def evaluate_listing(conn, listing_id: str) -> dict:
    """AI-assisted listing evaluation: quality score and market price comparison."""
    cur = conn.cursor()

    # Fetch listing
    cur.execute(
        """
        SELECT id, crop_name, quantity, unit, price_per_unit,
               quality_grade, harvest_date, location_id
        FROM marketplace_listing
        WHERE id = %s
        """,
        (listing_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": f"listing {listing_id} not found"}

    listing = dict(zip(cols, row))

    # Fetch recent prices for same crop
    cur.execute(
        """
        SELECT price, quality_grade
        FROM marketplace_price_observation
        WHERE crop_name = %s
        ORDER BY observed_at DESC
        LIMIT 50
        """,
        (listing["crop_name"],),
    )
    cols = [d[0] for d in cur.description]
    price_rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Fetch historical yield for this location/crop
    cur.execute(
        """
        SELECT AVG(yield_amount), STDDEV(yield_amount)
        FROM harvest_yield_observation
        WHERE location_id = %s AND crop_name = %s
          AND status IN ('verified', 'published')
        """,
        (listing["location_id"], listing["crop_name"]),
    )
    yield_row = cur.fetchone()
    avg_yield = float(yield_row[0]) if yield_row and yield_row[0] else None
    std_yield = float(yield_row[1]) if yield_row and yield_row[1] else None

    cur.close()

    # Quality score (0-100) based on grade and market comparison
    quality_map = {"A+": 95, "A": 85, "B+": 75, "B": 65, "C": 50}
    grade_score = quality_map.get(listing.get("quality_grade"), 60)

    # Price comparison
    if price_rows:
        market_prices = [float(p["price"]) for p in price_rows if p["price"]]
        if market_prices and listing["price_per_unit"]:
            avg_market = sum(market_prices) / len(market_prices)
            min_market = min(market_prices)
            max_market = max(market_prices)
            listing_price = float(listing["price_per_unit"])

            if listing_price <= avg_market * 0.9:
                competitiveness = "below_market"
                price_score = 80
            elif listing_price >= avg_market * 1.1:
                competitiveness = "above_market"
                price_score = 40
            else:
                competitiveness = "at_market"
                price_score = 70

            market_comparison = {
                "avg_market_price": round(avg_market, 4),
                "min_market_price": round(min_market, 4),
                "max_market_price": round(max_market, 4),
                "listing_price": listing_price,
                "competitiveness": competitiveness,
                "price_deviation_pct": round((listing_price - avg_market) / max(avg_market, 0.01) * 100, 1),
            }
        else:
            price_score = 60
            market_comparison = None
    else:
        price_score = 60
        market_comparison = None

    # Harvest freshness
    if listing.get("harvest_date"):
        days_old = (date.today() - listing["harvest_date"]).days
        freshness_score = max(0, 100 - days_old * 2)
    else:
        days_old = None
        freshness_score = 50

    # Overall score
    overall = round((grade_score * 0.35 + price_score * 0.35 + freshness_score * 0.30), 1)

    if overall >= 80:
        recommendation = "list_now"
    elif overall >= 60:
        recommendation = "adjust_price"
    else:
        recommendation = "hold_or_improve_quality"

    return {
        "listing_id": listing_id,
        "crop_name": listing["crop_name"],
        "evaluation": {
            "overall_score": overall,
            "quality_score": grade_score,
            "price_score": price_score,
            "freshness_score": freshness_score,
            "harvest_age_days": days_old,
        },
        "market_comparison": market_comparison,
        "recommendation": recommendation,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Digital marketplace for agricultural produce")
    sub = parser.add_subparsers(dest="command")

    # create-listing
    cl = sub.add_parser("create-listing", help="Create a produce listing")
    cl.add_argument("--location-id", required=True)
    cl.add_argument("--crop", required=True)
    cl.add_argument("--quantity", type=float, required=True)
    cl.add_argument("--unit", default="kg")
    cl.add_argument("--price", type=float, dest="price_per_unit")
    cl.add_argument("--grade", dest="quality_grade")
    cl.add_argument("--harvest-date", help="Harvest date YYYY-MM-DD")
    cl.add_argument("--description")
    cl.add_argument("--json", action="store_true")

    # update-listing
    ul = sub.add_parser("update-listing", help="Update a listing")
    ul.add_argument("--listing-id", required=True)
    ul.add_argument("--status")
    ul.add_argument("--price", type=float, dest="price_per_unit")
    ul.add_argument("--quantity", type=float)
    ul.add_argument("--grade", dest="quality_grade")
    ul.add_argument("--json", action="store_true")

    # get-listing
    gl = sub.add_parser("get-listing", help="Get listing details")
    gl.add_argument("--listing-id", required=True)
    gl.add_argument("--json", action="store_true")

    # list-active
    la = sub.add_parser("list-active", help="List active listings")
    la.add_argument("--location-id")
    la.add_argument("--crop")
    la.add_argument("--limit", type=int, default=50)
    la.add_argument("--offset", type=int, default=0)
    la.add_argument("--json", action="store_true")

    # create-buyer
    cb = sub.add_parser("create-buyer", help="Register a buyer")
    cb.add_argument("--name", required=True)
    cb.add_argument("--type", dest="buyer_type", default="individual")
    cb.add_argument("--location")
    cb.add_argument("--json", action="store_true")

    # record-price
    rp = sub.add_parser("record-price", help="Record price observation")
    rp.add_argument("--crop", required=True)
    rp.add_argument("--market", required=True)
    rp.add_argument("--price", type=float, required=True)
    rp.add_argument("--grade", dest="quality_grade")
    rp.add_argument("--unit", default="kg")
    rp.add_argument("--currency", default="USD")
    rp.add_argument("--json", action="store_true")

    # price-trends
    pt = sub.add_parser("price-trends", help="Get price trends")
    pt.add_argument("--crop", required=True)
    pt.add_argument("--days", type=int, default=30)
    pt.add_argument("--json", action="store_true")

    # create-order
    co = sub.add_parser("create-order", help="Create a buy order")
    co.add_argument("--listing-id", required=True)
    co.add_argument("--buyer-id", required=True)
    co.add_argument("--quantity", type=float, required=True)
    co.add_argument("--price", type=float, dest="offered_price")
    co.add_argument("--notes")
    co.add_argument("--json", action="store_true")

    # update-order
    uo = sub.add_parser("update-order", help="Update order status")
    uo.add_argument("--order-id", required=True)
    uo.add_argument("--status", required=True)
    uo.add_argument("--notes")
    uo.add_argument("--json", action="store_true")

    # track-shipment
    ts = sub.add_parser("track-shipment", help="Track shipment")
    ts.add_argument("--order-id", required=True)
    ts.add_argument("--location")
    ts.add_argument("--temperature", type=float)
    ts.add_argument("--humidity", type=float)
    ts.add_argument("--carrier")
    ts.add_argument("--tracking-number")
    ts.add_argument("--json", action="store_true")

    # market-overview
    mo = sub.add_parser("market-overview", help="Market overview")
    mo.add_argument("--location-id", required=True)
    mo.add_argument("--json", action="store_true")

    # create-alert
    ca = sub.add_parser("create-alert", help="Create price alert")
    ca.add_argument("--location-id", required=True)
    ca.add_argument("--crop", required=True)
    ca.add_argument("--threshold", type=float, required=True)
    ca.add_argument("--direction", choices=["above", "below"], default="above")
    ca.add_argument("--json", action="store_true")

    # evaluate
    ev = sub.add_parser("evaluate", help="Evaluate listing")
    ev.add_argument("--listing-id", required=True)
    ev.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if not args.command:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "create-listing":
            hd = date.fromisoformat(args.harvest_date) if args.harvest_date else None
            result = create_listing(
                db, args.location_id, args.crop, args.quantity,
                unit=args.unit, price_per_unit=args.price_per_unit,
                quality_grade=args.quality_grade, harvest_date=hd,
                description=args.description,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_listing(result)
            print(output)

        elif args.command == "update-listing":
            updates = {}
            if args.status:
                updates["status"] = args.status
            if args.price_per_unit is not None:
                updates["price_per_unit"] = args.price_per_unit
            if args.quantity is not None:
                updates["quantity"] = args.quantity
            if args.quality_grade:
                updates["quality_grade"] = args.quality_grade
            result = update_listing(db, args.listing_id, updates)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_update(result)
            print(output)

        elif args.command == "get-listing":
            result = get_listing(db, args.listing_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_detail(result)
            print(output)

        elif args.command == "list-active":
            result = list_active_listings(db, args.location_id, args.crop, args.limit, args.offset)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_listings(result)
            print(output)

        elif args.command == "create-buyer":
            result = create_buyer_profile(db, args.name, args.buyer_type, args.location)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_buyer(result)
            print(output)

        elif args.command == "record-price":
            result = record_price(
                db, args.crop, args.market, args.price,
                quality_grade=args.quality_grade, unit=args.unit,
                currency=args.currency,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_price(result)
            print(output)

        elif args.command == "price-trends":
            result = get_price_trends(db, args.crop, args.days)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_trends(result)
            print(output)

        elif args.command == "create-order":
            result = create_order(
                db, args.listing_id, args.buyer_id, args.quantity,
                offered_price=args.offered_price, notes=args.notes,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_order(result)
            print(output)

        elif args.command == "update-order":
            result = update_order_status(db, args.order_id, args.status, args.notes)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_update(result)
            print(output)

        elif args.command == "track-shipment":
            result = track_shipment(
                db, args.order_id, location=args.location,
                temperature=args.temperature, humidity=args.humidity,
                carrier=args.carrier, tracking_number=args.tracking_number,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_tracking(result)
            print(output)

        elif args.command == "market-overview":
            result = get_market_overview(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_overview(result)
            print(output)

        elif args.command == "create-alert":
            result = create_price_alert(
                db, args.location_id, args.crop, args.threshold,
                direction=args.direction,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_alert(result)
            print(output)

        elif args.command == "evaluate":
            result = evaluate_listing(db, args.listing_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_evaluation(result)
            print(output)

    finally:
        db.close()


def _format_listing(r: dict) -> str:
    return (
        f"Listing created: {r['crop_name']} {r['quantity']} {r['unit']} "
        f"@ {r['price_per_unit'] or '?'} ({r['quality_grade'] or 'ungraded'}) [{r['status']}]"
    )


def _format_update(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return f"Updated listing {r['listing_id'][:8]}... — {r['updated_fields']}"


def _format_detail(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Listing {r['id'][:8]}... — {r['crop_name']}\n"
        f"  Quantity: {r['quantity']} {r['unit']}\n"
        f"  Price: {r['price_per_unit'] or 'N/A'}\n"
        f"  Grade: {r['quality_grade'] or 'ungraded'}\n"
        f"  Status: {r['status']}\n"
        f"  Harvest: {r['harvest_date'] or 'N/A'}"
    )


def _format_listings(r: dict) -> str:
    lines = [f"Active Listings ({r['total']} total):"]
    for l in r["listings"]:
        lines.append(
            f"  {l['crop_name']:15s} {l['quantity']:>8.0f} {l['unit']:>4s} "
            f"@ {l.get('price_per_unit') or 'N/A':>8}  [{l.get('quality_grade') or '-'}]"
        )
    return "\n".join(lines)


def _format_buyer(r: dict) -> str:
    return f"Buyer registered: {r['name']} ({r['buyer_type']}) [{r['status']}]"


def _format_price(r: dict) -> str:
    return (
        f"Price recorded: {r['crop_name']} {r['price']} {r['currency']}/{r['unit']} "
        f"at {r['market_name']} [{r['quality_grade'] or 'any grade'}]"
    )


def _format_trends(r: dict) -> str:
    if r["data_points"] == 0:
        return f"Price trends for {r['crop_name']}: no data"
    arrow = "↑" if r["trend"] == "increasing" else "↓" if r["trend"] == "decreasing" else "→"
    return (
        f"Price Trends — {r['crop_name']} ({r['data_points']} observations, {r['days']}d)\n"
        f"  {arrow} Trend: {r['trend']} ({r['change_pct']:+.1f}%)\n"
        f"  Avg: {r['avg_price']}  Min: {r['min_price']}  Max: {r['max_price']}\n"
        f"  Latest: {r['latest_price']}"
    )


def _format_order(r: dict) -> str:
    return (
        f"Order created: {r['order_id'][:8]}... — {r['quantity']} units "
        f"@ {r['offered_price'] or '?'} = {r['total_amount'] or '?'} [{r['status']}]"
    )


def _format_tracking(r: dict) -> str:
    parts = [f"Shipment tracked for order {r['order_id'][:8]}..."]
    if r.get("location"):
        parts.append(f"  Location: {r['location']}")
    if r.get("carrier"):
        parts.append(f"  Carrier: {r['carrier']} ({r['tracking_number'] or 'N/A'})")
    if r.get("temperature") is not None:
        parts.append(f"  Temp: {r['temperature']}°C  Humidity: {r['humidity']}%")
    return "\n".join(parts)


def _format_overview(r: dict) -> str:
    lines = [
        f"Market Overview — {r['location_id'][:8]}...",
        f"  Active listings: {r['active_listings']}  Total qty: {r['total_quantity_listed']}",
    ]
    for c in r["listings_by_crop"]:
        lines.append(f"  {c['crop_name']:15s} {c['count']:>3} listings  avg price: {c['avg_price'] or 'N/A'}")
    if r["order_status_summary"]:
        lines.append("  Orders: " + "  ".join(f"{k}={v}" for k, v in r["order_status_summary"].items()))
    return "\n".join(lines)


def _format_alert(r: dict) -> str:
    return (
        f"Price alert created: {r['crop_name']} {r['direction']} {r['threshold']} "
        f"{r['currency']}/{r['unit']} [{r['status']}]"
    )


def _format_evaluation(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    ev = r["evaluation"]
    lines = [
        f"Evaluation — {r['crop_name']} (listing {r['listing_id'][:8]}...)",
        f"  Overall score: {ev['overall_score']}/100",
        f"  Quality: {ev['quality_score']}  Price: {ev['price_score']}  Freshness: {ev['freshness_score']}",
    ]
    if r.get("market_comparison"):
        mc = r["market_comparison"]
        lines.append(
            f"  Market avg: {mc['avg_market_price']}  Listing: {mc['listing_price']} "
            f"({mc['price_deviation_pct']:+.1f}%) — {mc['competitiveness']}"
        )
    lines.append(f"  Recommendation: {r['recommendation']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
