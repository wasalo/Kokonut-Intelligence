"""Demand analytics: demand forecasting, market sizing, demand trends, buyer segmentation, production-demand matching."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_demand_forecast(conn, location_id: str, forecast_horizon_months: int = 12) -> dict[str, Any]:
    """Compute demand forecast from historical sales and buyer signals.

    Uses exponential smoothing with seasonal decomposition for time-series forecasting.
    """
    cur = conn.cursor()

    # Historical monthly sales by crop
    cur.execute(
        """
        SELECT c.name AS crop_name, c.id AS crop_id,
               DATE_TRUNC('month', se.sale_date) AS month,
               SUM(se.quantity) AS total_quantity,
               SUM(se.total_amount) AS total_revenue
        FROM sales_event se
        JOIN crop_cycle cc ON se.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
        GROUP BY c.name, c.id, DATE_TRUNC('month', se.sale_date)
        ORDER BY c.name, month
        """,
        (location_id,),
    )
    historical = cur.fetchall()

    # Buyer pipeline demand
    cur.execute(
        """
        SELECT c.name AS crop_name, c.id AS crop_id,
               SUM(bds.quantity_requested) AS pipeline_quantity,
               SUM(bds.price_offered * bds.quantity_requested) AS pipeline_value,
               COUNT(*) AS signal_count
        FROM buyer_demand_signal bds
        LEFT JOIN crop c ON bds.crop_id = c.id
        WHERE bds.location_id = %s AND bds.status IN ('verified', 'published')
          AND bds.commitment_level IN ('firm', 'probable')
        GROUP BY c.name, c.id
        """,
        (location_id,),
    )
    pipeline = cur.fetchall()
    cur.close()

    # Build forecast per crop
    forecasts = []
    crop_data = defaultdict(list)
    for h in historical:
        crop_data[h[0]].append({
            "month": h[2],
            "quantity": float(h[3] or 0),
            "revenue": float(h[4] or 0),
        })

    for crop_name, months in crop_data.items():
        if len(months) < 3:
            continue  # Need at least 3 months for simple smoothing

        quantities = [m["quantity"] for m in months]
        avg = statistics.mean(quantities)
        std = statistics.stdev(quantities) if len(quantities) > 1 else avg * 0.2

        # Simple exponential smoothing (alpha=0.3)
        alpha = 0.3
        smoothed = quantities[0]
        for q in quantities[1:]:
            smoothed = alpha * q + (1 - alpha) * smoothed

        # Forecast: flat forecast with confidence bands
        forecast_qty = smoothed
        forecast_low = forecast_qty * 0.8
        forecast_high = forecast_qty * 1.2

        # Find pipeline demand for this crop
        pipeline_qty = 0
        for p in pipeline:
            if p[0] == crop_name:
                pipeline_qty = float(p[2] or 0)
                break

        total_demand = forecast_qty + pipeline_qty

        forecasts.append({
            "crop_name": crop_name,
            "forecast_type": "time_series",
            "historical_avg_monthly": round(avg, 2),
            "smoothed_estimate": round(forecast_qty, 2),
            "pipeline_demand": round(pipeline_qty, 2),
            "total_demand": round(total_demand, 2),
            "confidence_low": round(forecast_low, 2),
            "confidence_high": round(forecast_high, 2),
            "data_points": len(months),
        })

    result = {
        "location_id": location_id,
        "forecast_horizon_months": forecast_horizon_months,
        "total_crops_forecasted": len(forecasts),
        "forecasts": forecasts,
    }

    logger.info("Demand forecast for %s: %d crops forecasted", location_id, len(forecasts))
    return result


def compute_market_sizing(conn, location_id: str, crop_id: str | None = None) -> dict[str, Any]:
    """Compute TAM/SAM/SOM market size estimates."""
    cur = conn.cursor()

    where_clause = "WHERE mse.location_id = %s AND mse.status IN ('verified', 'published')"
    params = [location_id]
    if crop_id:
        where_clause += " AND mse.crop_id = %s"
        params.append(crop_id)

    cur.execute(
        f"""
        SELECT mse.id, c.name AS crop_name, mse.market_name, mse.market_scope,
               mse.tam_value, mse.sam_value, mse.som_value,
               mse.market_penetration_pct, mse.market_share_pct,
               mse.annual_growth_rate_pct, mse.estimation_method, mse.confidence_level
        FROM market_size_estimate mse
        LEFT JOIN crop c ON mse.crop_id = c.id
        {where_clause}
        ORDER BY mse.tam_value DESC
        """,
        params,
    )
    estimates = cur.fetchall()
    cur.close()

    total_tam = sum(float(e[4] or 0) for e in estimates)
    total_sam = sum(float(e[5] or 0) for e in estimates)
    total_som = sum(float(e[7] or 0) for e in estimates)

    result = {
        "location_id": location_id,
        "total_estimates": len(estimates),
        "total_tam_usd": round(total_tam, 2),
        "total_sam_usd": round(total_sam, 2),
        "total_som_usd": round(total_som, 2),
        "estimates": [
            {
                "crop_name": e[1],
                "market_name": e[2],
                "market_scope": e[3],
                "tam_value": float(e[4]) if e[4] else 0,
                "sam_value": float(e[5]) if e[5] else 0,
                "som_value": float(e[7]) if e[7] else 0,
                "penetration_pct": float(e[8]) if e[8] else 0,
                "growth_rate_pct": float(e[10]) if e[10] else 0,
                "method": e[11],
                "confidence": e[12],
            }
            for e in estimates
        ],
    }

    logger.info("Market sizing for %s: TAM=$%.0f, SAM=$%.0f, SOM=$%.0f",
                location_id, total_tam, total_sam, total_som)
    return result


def compute_demand_trends(conn, location_id: str, crop_id: str | None = None) -> dict[str, Any]:
    """Compute demand trends: seasonal patterns, price elasticity, moving averages."""
    cur = conn.cursor()

    # Monthly sales by crop
    cur.execute(
        """
        SELECT c.name AS crop_name,
               EXTRACT(MONTH FROM se.sale_date) AS month,
               SUM(se.quantity) AS total_quantity,
               AVG(se.price_per_unit) AS avg_price
        FROM sales_event se
        JOIN crop_cycle cc ON se.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
        GROUP BY c.name, EXTRACT(MONTH FROM se.sale_date)
        ORDER BY c.name, month
        """,
        (location_id,),
    )
    monthly_data = cur.fetchall()
    cur.close()

    # Group by crop
    crop_monthly = {}
    for row in monthly_data:
        crop_name = row[0]
        if crop_name not in crop_monthly:
            crop_monthly[crop_name] = {}
        crop_monthly[crop_name][int(row[1])] = {
            "quantity": float(row[2] or 0),
            "price": float(row[3] or 0),
        }

    trends = []
    for crop_name, months in crop_monthly.items():
        if len(months) < 3:
            continue

        quantities = [months[m]["quantity"] for m in sorted(months.keys())]
        avg = statistics.mean(quantities)
        peak_month = max(months, key=lambda m: months[m]["quantity"])
        trough_month = min(months, key=lambda m: months[m]["quantity"])

        # Seasonal indices (12-month)
        seasonal_indices = {}
        for m, data in months.items():
            seasonal_indices[m] = data["quantity"] / avg if avg > 0 else 1

        # Moving averages
        ma_3 = statistics.mean(quantities[-3:]) if len(quantities) >= 3 else avg
        ma_6 = statistics.mean(quantities[-6:]) if len(quantities) >= 6 else avg
        ma_12 = statistics.mean(quantities[-12:]) if len(quantities) >= 12 else avg

        # Coefficient of variation
        cv = statistics.stdev(quantities) / avg if avg > 0 and len(quantities) > 1 else 0

        trends.append({
            "crop_name": crop_name,
            "analysis_type": "seasonal_pattern",
            "data_points": len(months),
            "avg_monthly_demand": round(avg, 2),
            "seasonal_indices": {str(k): round(v, 3) for k, v in sorted(seasonal_indices.items())},
            "peak_month": peak_month[0],
            "trough_month": trough_month[0],
            "moving_avg_3m": round(ma_3, 2),
            "moving_avg_6m": round(ma_6, 2),
            "moving_avg_12m": round(ma_12, 2),
            "coefficient_of_variation": round(cv, 4),
            "trend_direction": "increasing" if len(quantities) > 1 and quantities[-1] > quantities[0] else "decreasing" if len(quantities) > 1 and quantities[-1] < quantities[0] else "stable",
        })

    result = {
        "location_id": location_id,
        "total_crops_analyzed": len(trends),
        "trends": trends,
    }

    logger.info("Demand trends for %s: %d crops analyzed", location_id, len(trends))
    return result


def compute_buyer_segmentation(conn, location_id: str) -> dict[str, Any]:
    """Segment buyers by behavior, value, and retention."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT p.id AS partner_id, p.name AS buyer_name, p.partner_type,
               COUNT(se.id) AS order_count,
               SUM(se.total_amount) AS total_revenue,
               AVG(se.price_per_unit) AS avg_price,
               AVG(se.quantity) AS avg_quantity,
               MAX(se.sale_date) AS last_order_date,
               MIN(se.sale_date) AS first_order_date
        FROM sales_event se
        LEFT JOIN partner p ON se.partner_id = p.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
          AND se.partner_id IS NOT NULL
        GROUP BY p.id, p.name, p.partner_type
        ORDER BY total_revenue DESC
        """,
        (location_id,),
    )
    buyers = cur.fetchall()
    cur.close()

    if not buyers:
        return {"location_id": location_id, "total_buyers": 0, "segments": []}

    total_revenue = sum(float(b[3] or 0) for b in buyers)
    avg_revenue = total_revenue / len(buyers) if buyers else 0

    segments = []
    for b in buyers:
        revenue = float(b[3] or 0)
        share = revenue / total_revenue if total_revenue > 0 else 0

        # Simple segmentation: high value = top 30% by revenue
        threshold_70 = total_revenue * 0.7
        cumulative = 0
        rank = 0
        for bb in sorted(buyers, key=lambda x: float(x[3] or 0), reverse=True):
            cumulative += float(bb[3] or 0)
            rank += 1
            if bb[0] == b[0]:
                break

        if cumulative <= threshold_70:
            segment = "high_value"
        elif revenue > avg_revenue:
            segment = "medium_value"
        else:
            segment = "low_value"

        segments.append({
            "partner_id": str(b[0]),
            "buyer_name": b[1],
            "buyer_type": b[2],
            "order_count": b[4],
            "total_revenue": round(revenue, 2),
            "revenue_share_pct": round(share * 100, 2),
            "avg_order_value": round(float(b[5] or 0), 2),
            "avg_quantity": round(float(b[6] or 0), 2),
            "last_order_date": str(b[7]) if b[7] else None,
            "first_order_date": str(b[8]) if b[8] else None,
            "segment": segment,
        })

    result = {
        "location_id": location_id,
        "total_buyers": len(buyers),
        "total_revenue": round(total_revenue, 2),
        "segments": segments,
        "segment_summary": {
            "high_value": sum(1 for s in segments if s["segment"] == "high_value"),
            "medium_value": sum(1 for s in segments if s["segment"] == "medium_value"),
            "low_value": sum(1 for s in segments if s["segment"] == "low_value"),
        },
    }

    logger.info("Buyer segmentation for %s: %d buyers, $%.2f total revenue",
                location_id, len(buyers), total_revenue)
    return result


def compute_production_market_match(conn, location_id: str, crop_id: str | None = None) -> dict[str, Any]:
    """Match production capacity to buyer demand (supply-demand gap)."""
    cur = conn.cursor()

    # Get projected production from forecast_output
    cur.execute(
        """
        SELECT c.name AS crop_name, c.id AS crop_id,
               SUM(fo.value) AS projected_tonnes
        FROM forecast_output fo
        JOIN crop c ON fo.crop_id = c.id
        WHERE fo.location_id = %s AND fo.metric_name = 'total_yield_tonnes'
        GROUP BY c.name, c.id
        """,
        (location_id,),
    )
    production = {str(r[1]): {"name": r[0], "projected": float(r[2] or 0)} for r in cur.fetchall()}

    # Get confirmed demand from buyer signals
    cur.execute(
        """
        SELECT c.id AS crop_id, c.name AS crop_name,
               SUM(bds.quantity_requested) AS confirmed_demand
        FROM buyer_demand_signal bds
        LEFT JOIN crop c ON bds.crop_id = c.id
        WHERE bds.location_id = %s AND bds.status IN ('verified', 'published')
          AND bds.commitment_level IN ('firm', 'probable')
        GROUP BY c.id, c.name
        """,
        (location_id,),
    )
    confirmed = {str(r[0]): {"name": r[1], "demand": float(r[2] or 0)} for r in cur.fetchall()}

    # Get pipeline demand (possible + exploratory)
    cur.execute(
        """
        SELECT c.id AS crop_id,
               SUM(bds.quantity_requested) AS pipeline_demand
        FROM buyer_demand_signal bds
        LEFT JOIN crop c ON bds.crop_id = c.id
        WHERE bds.location_id = %s AND bds.status IN ('verified', 'published')
          AND bds.commitment_level IN ('possible', 'exploratory')
        GROUP BY c.id
        """,
        (location_id,),
    )
    pipeline = {str(r[0]): float(r[1] or 0) for r in cur.fetchall()}

    # Match supply to demand
    matches = []
    all_crops = set(list(production.keys()) + list(confirmed.keys()))
    for crop_id_key in all_crops:
        prod = production.get(crop_id_key, {})
        conf = confirmed.get(crop_id_key, {})
        pipe = pipeline.get(crop_id_key, 0)

        projected = prod.get("projected", 0)
        confirmed_demand = conf.get("demand", 0)
        total_demand = confirmed_demand + pipe
        gap = total_demand - projected
        coverage = (confirmed_demand / projected * 100) if projected > 0 else 0

        matches.append({
            "crop_name": prod.get("name") or conf.get("name"),
            "projected_production_tonnes": round(projected, 2),
            "confirmed_demand_tonnes": round(confirmed_demand, 2),
            "pipeline_demand_tonnes": round(pipe, 2),
            "total_demand_tonnes": round(total_demand, 2),
            "supply_demand_gap_tonnes": round(gap, 2),
            "gap_status": "surplus" if gap < 0 else "shortfall" if gap > 0 else "balanced",
            "demand_coverage_pct": round(coverage, 1),
        })

    result = {
        "location_id": location_id,
        "total_crops_analyzed": len(matches),
        "matches": matches,
        "summary": {
            "total_surplus": sum(1 for m in matches if m["supply_demand_gap_tonnes"] < 0),
            "total_shortfall": sum(1 for m in matches if m["supply_demand_gap_tonnes"] > 0),
            "total_balanced": sum(1 for m in matches if m["supply_demand_gap_tonnes"] == 0),
        },
    }

    logger.info("Production-demand match for %s: %d crops analyzed", location_id, len(matches))
    return result
