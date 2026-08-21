#!/usr/bin/env python3
"""
Digital Marketplace for Agricultural Produce

Manages produce listings, buyer profiles, price observations, orders,
logistics tracking, price alerts, and AI-assisted listing evaluation.

Usage:
    python -m services.analytics.marketplace create-listing --location-id UUID --crop Lettuce --quantity 500 --unit kg --price 0.50 --grade A
    python -m services.analytics.marketplace list-active --location-id UUID --crop Lettuce
    python -m services.analytics.marketplace record-price --crop Lettuce --market "Adelphi Coop" --price 0.55 --grade A
    python -m services.analytics.marketplace price-trends --crop Lettuce --days 30
    python -m services.analytics.marketplace create-order --listing-id UUID --buyer-id UUID --quantity 200
    python -m services.analytics.marketplace market-overview --location-id UUID

NOTE: the canonical schema uses `market_*` tables (142_marketplace.sql) and
references crops by `crop_id` (FK to `crop`). This module keeps its
public `crop_name` API and resolves names to `crop_id` internally.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.marketplace")

# Listings are "active" when published and not yet sold/expired. The canonical
# `market_listing.status` has no literal 'active' value, so we use a predicate.
ACTIVE_LISTING_WHERE = (
    "ml.status = 'published' AND ml.sold_at IS NULL "
    "AND (ml.expires_at IS NULL OR ml.expires_at > now())"
)


def _resolve_crop_id(conn, crop_name: str) -> Optional[str]:
    """Resolve a human crop name to its canonical `crop_id` UUID."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM crop WHERE name = %s", (crop_name,))
        row = cur.fetchone()
    return str(row[0]) if row else None


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
    crop_id = _resolve_crop_id(conn, crop_name)
    if not crop_id:
        raise ValueError(f"crop not found: {crop_name}")

    cur = conn.cursor()
    listing_id = str(uuid.uuid4())
    harvest_date = harvest_date or date.today()
    listing_metadata = dict(metadata or {})
    listing_metadata.setdefault("harvest_date", harvest_date.isoformat())
    title = listing_metadata.pop("title", None) or f"{crop_name} listing"

    cur.execute(
        """
        INSERT INTO market_listing
            (id, location_id, crop_id, title, quantity, unit, price_per_unit,
             quality_grade, description, image_urls, status, published_at,
             metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'published', %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            listing_id, location_id, crop_id, title, quantity, unit,
            price_per_unit, quality_grade, description, images or [],
            datetime.now(timezone.utc), json.dumps(listing_metadata),
            datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
        "status": "published",
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
        "description", "images", "image_urls", "metadata",
    }
    set_clauses = []
    params = []
    for key, value in updates.items():
        if key not in allowed_fields:
            continue
        if key in ("images", "image_urls"):
            set_clauses.append("image_urls = %s")
            params.append(value or [])
        elif key == "metadata":
            set_clauses.append("metadata = %s::jsonb")
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
        f"UPDATE market_listing SET {', '.join(set_clauses)} WHERE id = %s RETURNING id",
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
        SELECT ml.id, ml.location_id, c.name AS crop_name, ml.quantity, ml.unit,
               ml.price_per_unit, ml.quality_grade, ml.available_from AS harvest_date,
               ml.description, ml.image_urls AS images, ml.status, ml.metadata,
               ml.created_at, ml.updated_at
        FROM market_listing ml
        LEFT JOIN crop c ON c.id = ml.crop_id
        WHERE ml.id = %s
        """,
        (listing_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": f"listing {listing_id} not found"}

    result = dict(zip(cols, row))
    result["crop_name"] = result["crop_name"] or "unknown"
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

    where = ACTIVE_LISTING_WHERE
    params = []
    if location_id:
        where += " AND ml.location_id = %s"
        params.append(location_id)
    if crop_name:
        crop_id = _resolve_crop_id(conn, crop_name)
        if not crop_id:
            cur.close()
            return {"listings": [], "total": 0, "limit": limit, "offset": offset}
        where += " AND ml.crop_id = %s"
        params.append(crop_id)

    cur.execute(
        f"""
        SELECT ml.id, ml.location_id, c.name AS crop_name, ml.quantity, ml.unit,
               ml.price_per_unit, ml.quality_grade, ml.available_from AS harvest_date, ml.created_at
        FROM market_listing ml
        LEFT JOIN crop c ON c.id = ml.crop_id
        WHERE {where}
        ORDER BY ml.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    for r in rows:
        r["crop_name"] = r["crop_name"] or "unknown"
        r["harvest_date"] = r["harvest_date"].isoformat() if r["harvest_date"] else None
        r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None

    cur.execute(
        f"SELECT COUNT(*) FROM market_listing ml WHERE {where}",
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
    party_id: str = None,
) -> dict:
    """Register a buyer on the marketplace."""
    cur = conn.cursor()
    buyer_id = str(uuid.uuid4())
    contact_info = contact_info or {}
    preferences = preferences or {}

    cur.execute(
        """
        INSERT INTO buyer_profile
             (id, party_id, name, buyer_type, address, contact_name, contact_email,
              contact_phone, crops_of_interest, metadata, status, created_at)
         VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active', %s)
        RETURNING id
        """,
        (
            buyer_id, party_id, name, buyer_type, location,
            contact_info.get("name"),
            contact_info.get("email"),
            contact_info.get("phone"),
             preferences.get("crops", preferences) if isinstance(preferences.get("crops", preferences), list) else list(preferences.get("crops", preferences).keys()) if isinstance(preferences.get("crops", preferences), dict) else [str(preferences.get("crops", preferences))],
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
    crop_id = _resolve_crop_id(conn, crop_name)
    if not crop_id:
        raise ValueError(f"crop not found: {crop_name}")

    cur = conn.cursor()
    price_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO price_observation
            (id, crop_id, market_name, price_per_unit, price_date,
             unit, currency, source, location_id, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            price_id, crop_id, market_name, price,
            datetime.now(timezone.utc).date(),
            unit, currency, source, None,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
    crop_id = _resolve_crop_id(conn, crop_name)

    cur.execute(
        """
        SELECT po.price_per_unit AS price, po.quality_grade, po.market_name,
               po.price_date AS observed_at, c.name AS crop_name
        FROM price_observation po
        LEFT JOIN crop c ON c.id = po.crop_id
        WHERE po.crop_id = %s AND po.price_date >= %s
        ORDER BY po.price_date
        """,
        (crop_id, cutoff.date() if crop_id else cutoff.date()),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
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

    cur.execute(
        """
        SELECT seller_id, location_id, unit, price_per_unit
        FROM market_listing WHERE id = %s
        """,
        (listing_id,),
    )
    listing = cur.fetchone()
    if not listing:
        cur.close()
        return {"error": f"listing {listing_id} not found"}

    seller_id, location_id, unit, list_price = listing
    if offered_price is None:
        offered_price = float(list_price) if list_price else None
    total_amount = round(offered_price * quantity, 2) if offered_price else None

    cur.execute(
        """
        INSERT INTO market_order
            (id, listing_id, buyer_id, seller_id, location_id, quantity,
             unit, price_per_unit, total_amount, currency, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'USD', 'pending', %s)
        RETURNING id
        """,
        (
            order_id, listing_id, buyer_id, seller_id, location_id,
            quantity, unit or "kg", offered_price, total_amount,
            datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
        UPDATE market_order
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

    shipment_meta = dict(metadata or {})
    shipment_meta.update({
        "order_id": order_id,
        "temperature": temperature,
        "humidity": humidity,
        "tracking_number": tracking_number,
    })

    cur.execute(
        """
        INSERT INTO logistics_tracking
            (id, order_id, carrier_name, tracking_number, estimated_arrival,
             current_location, temperature_min, temperature_max,
             humidity_min, humidity_max, status, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s::jsonb, %s, %s)
        RETURNING id
        """,
        (
            tracking_id, order_id, carrier, tracking_number, estimated_arrival,
            location, temperature, temperature, humidity, humidity,
            json.dumps(shipment_meta), datetime.now(timezone.utc), datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
        f"""
        SELECT COUNT(*), COALESCE(SUM(ml.quantity), 0)
        FROM market_listing ml
        WHERE ml.location_id = %s AND {ACTIVE_LISTING_WHERE}
        """,
        (location_id,),
    )
    listing_row = cur.fetchone()
    active_listings = int(listing_row[0])
    total_quantity = float(listing_row[1])

    # Listings by crop
    cur.execute(
        f"""
        SELECT c.name AS crop_name, COUNT(*) AS count, SUM(ml.quantity) AS total_qty,
               AVG(ml.price_per_unit) AS avg_price
        FROM market_listing ml
        LEFT JOIN crop c ON c.id = ml.crop_id
        WHERE ml.location_id = %s AND {ACTIVE_LISTING_WHERE}
        GROUP BY c.name
        ORDER BY total_qty DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    crop_listings = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Recent prices
    cur.execute(
        """
        SELECT c.name AS crop_name, AVG(po.price_per_unit) AS avg_price,
               MIN(po.price_per_unit) AS min_price,
               MAX(po.price_per_unit) AS max_price, COUNT(*) AS observations
        FROM price_observation po
        LEFT JOIN crop c ON c.id = po.crop_id
        WHERE po.price_date >= %s
        GROUP BY c.name
        ORDER BY observations DESC
        """,
        (datetime.now(timezone.utc).date() - timedelta(days=30),),
    )
    cols = [d[0] for d in cur.description]
    recent_prices = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Order status summary
    cur.execute(
        """
        SELECT o.status, COUNT(*) AS count
        FROM market_order o
        JOIN market_listing l ON o.listing_id = l.id
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
    crop_id = _resolve_crop_id(conn, crop_name)
    if not crop_id:
        raise ValueError(f"crop not found: {crop_name}")

    cur = conn.cursor()
    alert_id = str(uuid.uuid4())
    title = f"Price alert: {crop_name} {direction} {threshold} {currency}/{unit}"
    message = (
        f"Alert when {crop_name} price goes {direction} {threshold} {currency}/{unit}."
    )
    alert_meta = dict(metadata or {})
    alert_meta.update({
        "notify_email": notify_email,
        "currency": currency,
        "unit": unit,
        "direction": direction,
    })

    cur.execute(
        """
        INSERT INTO market_alert
            (id, location_id, crop_id, alert_type, severity, title, message,
             trigger_metric, trigger_condition, trigger_threshold, channel,
             status, metadata, created_at)
        VALUES (%s, %s, %s, 'price', 'info', %s, %s, 'price', %s, %s,
                'email', 'active', %s::jsonb, %s)
        RETURNING id
        """,
        (
            alert_id, location_id, crop_id, title, message,
            direction, threshold,
            json.dumps(alert_meta),
            datetime.now(timezone.utc),
        ),
    )
    row = cur.fetchone()
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
        SELECT ml.id, c.name AS crop_name, ml.quantity, ml.unit, ml.price_per_unit,
               ml.quality_grade, ml.available_from AS harvest_date, ml.location_id
        FROM market_listing ml
        LEFT JOIN crop c ON c.id = ml.crop_id
        WHERE ml.id = %s
        """,
        (listing_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": f"listing {listing_id} not found"}

    listing = dict(zip(cols, row))
    listing["crop_name"] = listing["crop_name"] or "unknown"

    crop_id = _resolve_crop_id(conn, listing["crop_name"])

    # Fetch recent prices for same crop
    if crop_id:
        cur.execute(
            """
            SELECT price_per_unit AS price, quality_grade
            FROM price_observation
            WHERE crop_id = %s
            ORDER BY price_date DESC
            LIMIT 50
            """,
            (crop_id,),
        )
        cols = [d[0] for d in cur.description]
        price_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    else:
        price_rows = []

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
