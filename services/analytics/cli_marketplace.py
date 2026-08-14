"""Digital marketplace (listings, orders, pricing) CLI.

Extracted from services.analytics.marketplace so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_marketplace --help
"""

import argparse
import json
from datetime import date

from .marketplace import (
    create_buyer_profile,
    create_listing,
    create_order,
    create_price_alert,
    evaluate_listing,
    get_listing,
    get_market_overview,
    get_price_trends,
    list_active_listings,
    record_price,
    track_shipment,
    update_listing,
    update_order_status,
)

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
    cb.add_argument("--preferences", default="{}")
    cb.add_argument("--contact-info", default="{}")
    cb.add_argument("--party-id")
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

    from ..ingestion.base import get_db

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
            result = create_buyer_profile(
                db, args.name, args.buyer_type, args.location,
                preferences=json.loads(args.preferences),
                contact_info=json.loads(args.contact_info),
                party_id=args.party_id,
            )
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
    if "error" in r:
        return f"Error: {r['error']}"
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

