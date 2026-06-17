"""Example: Query NOI snapshots for completed crop cycles.

Usage:
    KOKONUT_TOKEN=... python examples/query_noi.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kokonut import KokonutClient, ListOptions

BASE_URL = os.environ.get("KOKONUT_BASE_URL", "http://localhost:8055")
TOKEN = os.environ.get("KOKONUT_TOKEN")


def main() -> None:
    client = KokonutClient(BASE_URL, token=TOKEN)

    if not TOKEN:
        client.login("admin@example.com", os.environ.get("ADMIN_PASSWORD", "changeme"))

    crop_cycles = client.crop_cycles.list(
        ListOptions(
            filter={"status": {"_in": ["harvested", "completed"]}},
            sort=["-planting_date"],
            limit=5,
        )
    )

    print(f"Found {len(crop_cycles)} completed crop cycles\n")

    for cycle in crop_cycles:
        print(f"--- {cycle.get('cycle_name', cycle['id'])} ---")
        print(f"  Planted:    {cycle.get('planting_date', 'N/A')}")
        print(f"  Harvested:  {cycle.get('actual_harvest_date', 'N/A')}")
        print(f"  Yield:      {cycle.get('actual_yield', 'N/A')} {cycle.get('actual_yield_unit', '')}")

        harvests = client.harvest_events.list_by_crop_cycle(
            cycle["id"], ListOptions(sort=["-harvest_date"])
        )
        print(f"  Harvests:   {len(harvests)}")

        sales = client.sales_events.list_by_crop_cycle(
            cycle["id"], ListOptions(sort=["-sale_date"])
        )
        total_revenue = sum(s.get("total_amount", 0) or 0 for s in sales)
        print(f"  Sales:      {len(sales)}")
        print(f"  Revenue:    ${total_revenue:,.2f}")

        expenses = client.expense_events.list_by_crop_cycle(cycle["id"])
        total_expenses = sum(e.get("amount", 0) or 0 for e in expenses)
        print(f"  Expenses:   {len(expenses)}")
        print(f"  Costs:      ${total_expenses:,.2f}")

        noi = total_revenue - total_expenses
        margin = (noi / total_revenue * 100) if total_revenue > 0 else 0
        print(f"  NOI:        ${noi:,.2f} ({margin:.1f}% margin)\n")

    # Also query stored NOI snapshots
    reports = client.reports.list_by_type(
        "crop_noi", ListOptions(sort=["-created_at"], limit=5)
    )
    print(f"Recent NOI report snapshots: {len(reports)}")
    for report in reports:
        print(f"  {report['id']} - {report.get('created_at', 'N/A')}")
        if report.get("snapshot_hash"):
            print(f"    Hash: {report['snapshot_hash']}")


if __name__ == "__main__":
    main()
