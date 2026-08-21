"""Digital Cooperative Services CLI.

Extracted from services.analytics.cooperative so the domain module stays
focused on queries/business logic. Reachable via:

    python -m services.analytics.cli_cooperative create-coop --name "Adelphi Coop" ...
"""


import json

from ..common.commands import CommandLine
from .cooperative import (
    add_market_participant,
    add_member,
    add_purchase_participant,
    add_shared_asset,
    book_asset,
    create_collective_purchase,
    create_cooperative,
    create_market_order,
    get_asset_utilization,
    get_collective_orders,
    get_cooperative_summary,
    get_member_dashboard,
    list_cooperatives,
)


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

def _render(result, a, fmt):
    if a.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(fmt(result))


def _cmd_create_coop(db, a):
    return create_cooperative(
        db, a.name, a.type, a.location_id,
        governance_model=a.governance, description=a.description,
        mission_statement=a.mission,
    )


def _cmd_add_member(db, a):
    return add_member(
        db, a.cooperative_id, a.farmer_id,
        role=a.role, shares=a.shares, member_type=a.member_type,
        party_id=a.party_id,
    )


def _cmd_summary(db, a):
    return get_cooperative_summary(db, a.cooperative_id)


def _cmd_list(db, a):
    return list_cooperatives(db, a.location_id)


def _cmd_add_asset(db, a):
    return add_shared_asset(
        db, a.cooperative_id, a.name, a.type,
        a.daily_rate, description=a.description,
        capacity=a.capacity, capacity_unit=a.capacity_unit,
        hourly_rate=a.hourly_rate, purchase_price=a.purchase_price,
    )


def _cmd_book_asset(db, a):
    return book_asset(
        db, a.asset_id, a.membership_id,
        a.start, a.end, purpose=a.purpose,
        field_location=a.field_location,
    )


def _cmd_asset_utilization(db, a):
    return get_asset_utilization(db, a.cooperative_id)


def _cmd_create_purchase(db, a):
    return create_collective_purchase(
        db, a.cooperative_id, a.order_name, a.category,
        a.target_qty, a.unit, a.target_price,
        description=a.description, deadline=a.deadline,
    )


def _cmd_add_purchase_participant(db, a):
    return add_purchase_participant(
        db, a.purchase_id, a.membership_id,
        a.quantity, a.commitment,
    )


def _cmd_create_market_order(db, a):
    return create_market_order(
        db, a.cooperative_id, a.order_name, a.crop,
        a.quantity, a.unit, a.target_price,
        quality_grade=a.grade, description=a.description,
        delivery_date=a.delivery_date,
    )


def _cmd_add_market_participant(db, a):
    return add_market_participant(
        db, a.market_order_id, a.membership_id, a.quantity,
    )


def _cmd_collective_orders(db, a):
    return get_collective_orders(db, a.cooperative_id)


def _cmd_member_dashboard(db, a):
    return get_member_dashboard(db, a.farmer_id)


cli = CommandLine("cooperative", "Digital cooperative services")

cli.subcommand("create-coop", "Create cooperative") \
    .add("--name", required=True) \
    .add("--type", required=True, help="Type: marketing, input_purchase, equipment_sharing, processing") \
    .add("--location-id", required=True) \
    .add("--governance", default="one_member_one_vote",
         help="Governance model: one_member_one_vote, proportional, board_directors, delegated, hybrid") \
    .add("--description") \
    .add("--mission") \
    .add("--json", action="store_true") \
    .run(_cmd_create_coop) \
    .render_with(lambda r, a: _render(r, a, _format_coop))

cli.subcommand("add-member", "Add member") \
    .add("--cooperative-id", required=True) \
    .add("--farmer-id", required=True, help="Farmer name or ID") \
    .add("--role", default="member", help="Role: member, board_member, treasurer, secretary, chairperson, manager") \
    .add("--shares", type=int, default=1) \
    .add("--member-type", default="farmer", help="Type: farmer, associate, youth, women_group") \
    .add("--party-id", help="Canonical stakeholder party UUID") \
    .add("--json", action="store_true") \
    .run(_cmd_add_member) \
    .render_with(lambda r, a: _render(r, a, _format_member))

cli.subcommand("summary", "Cooperative summary") \
    .add("--cooperative-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_summary) \
    .render_with(lambda r, a: _render(r, a, _format_summary))

cli.subcommand("list", "List cooperatives") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_list) \
    .render_with(lambda r, a: _render(r, a, _format_list))

cli.subcommand("add-asset", "Add shared asset") \
    .add("--cooperative-id", required=True) \
    .add("--name", required=True) \
    .add("--type", required=True,
         help="Asset type: tractor, harvester, irrigation_system, storage_facility, processing_equipment, transport_vehicle, other") \
    .add("--daily-rate", type=float, required=True) \
    .add("--description") \
    .add("--capacity") \
    .add("--capacity-unit") \
    .add("--hourly-rate", type=float) \
    .add("--purchase-price", type=float) \
    .add("--json", action="store_true") \
    .run(_cmd_add_asset) \
    .render_with(lambda r, a: _render(r, a, _format_asset))

cli.subcommand("book-asset", "Book shared asset") \
    .add("--asset-id", required=True) \
    .add("--membership-id", required=True) \
    .add("--start", required=True, help="Start datetime YYYY-MM-DDTHH:MM") \
    .add("--end", required=True, help="End datetime YYYY-MM-DDTHH:MM") \
    .add("--purpose") \
    .add("--field-location") \
    .add("--json", action="store_true") \
    .run(_cmd_book_asset) \
    .render_with(lambda r, a: _render(r, a, _format_booking))

cli.subcommand("asset-utilization", "Asset utilization") \
    .add("--cooperative-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_asset_utilization) \
    .render_with(lambda r, a: _render(r, a, _format_utilization))

cli.subcommand("create-purchase", "Create collective purchase") \
    .add("--cooperative-id", required=True) \
    .add("--order-name", required=True) \
    .add("--category", required=True,
         help="Category: seeds, fertilizer, pesticide, herbicide, tools, fuel, feed, organic_inputs, other") \
    .add("--target-qty", type=float, required=True) \
    .add("--unit", required=True) \
    .add("--target-price", type=float, required=True) \
    .add("--description") \
    .add("--deadline") \
    .add("--json", action="store_true") \
    .run(_cmd_create_purchase) \
    .render_with(lambda r, a: _render(r, a, _format_purchase))

cli.subcommand("add-purchase-participant", "Add purchase participant") \
    .add("--purchase-id", required=True) \
    .add("--membership-id", required=True) \
    .add("--quantity", type=float, required=True) \
    .add("--commitment", type=float, required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_add_purchase_participant) \
    .render_with(lambda r, a: _render(r, a, _format_participant))

cli.subcommand("create-market-order", "Create collective market order") \
    .add("--cooperative-id", required=True) \
    .add("--order-name", required=True) \
    .add("--crop", required=True) \
    .add("--quantity", type=float, required=True) \
    .add("--unit", default="kg") \
    .add("--grade") \
    .add("--target-price", type=float, required=True) \
    .add("--description") \
    .add("--delivery-date") \
    .add("--json", action="store_true") \
    .run(_cmd_create_market_order) \
    .render_with(lambda r, a: _render(r, a, _format_market_order))

cli.subcommand("add-market-participant", "Add market order participant") \
    .add("--market-order-id", required=True) \
    .add("--membership-id", required=True) \
    .add("--quantity", type=float, required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_add_market_participant) \
    .render_with(lambda r, a: _render(r, a, _format_market_participant))

cli.subcommand("collective-orders", "Active collective orders") \
    .add("--cooperative-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_collective_orders) \
    .render_with(lambda r, a: _render(r, a, _format_orders))

cli.subcommand("member-dashboard", "Member dashboard") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_member_dashboard) \
    .render_with(lambda r, a: _render(r, a, _format_dashboard))


def main(argv=None):
    return cli.run(argv)


if __name__ == "__main__":
    main()

