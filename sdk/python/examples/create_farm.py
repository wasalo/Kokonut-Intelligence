"""Example: Create a location, farm, and plot via the Kokonut Python SDK.

Usage:
    KOKONUT_TOKEN=... python examples/create_farm.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kokonut import KokonutClient

BASE_URL = os.environ.get("KOKONUT_BASE_URL", "http://localhost:8055")
TOKEN = os.environ.get("KOKONUT_TOKEN")


def main() -> None:
    client = KokonutClient(BASE_URL, token=TOKEN)

    if not TOKEN:
        client.login("admin@example.com", "password123")

    location = client.locations.create({
        "name": "Finca El Paraiso",
        "slug": "finca-el-paraiso",
        "description": "Regenerative coffee and cacao farm in Huila, Colombia",
        "country": "Colombia",
        "region": "Huila",
        "baseline_revenue": 45000,
        "baseline_asset_value": 120000,
        "baseline_cash_flow": 12000,
        "status": "active",
    })
    print(f"Location created: {location['id']}")

    farm = client.farms.create({
        "location_id": location["id"],
        "name": "El Paraiso Main Farm",
        "slug": "el-paraiso-main",
        "farm_type": "operational",
        "total_area": 25,
        "area_unit": "ha",
        "status": "active",
    })
    print(f"Farm created: {farm['id']}")

    plot_a = client.plots.create({
        "farm_id": farm["id"],
        "name": "Plot A - Coffee",
        "slug": "plot-a-coffee",
        "area": 12,
        "area_unit": "ha",
        "soil_type": "clay_loam",
        "water_source": "spring_fed_irrigation",
        "status": "active",
    })
    print(f"Plot A created: {plot_a['id']}")

    plot_b = client.plots.create({
        "farm_id": farm["id"],
        "name": "Plot B - Cacao",
        "slug": "plot-b-cacao",
        "area": 8,
        "area_unit": "ha",
        "soil_type": "volcanic_loam",
        "water_source": "rainfed",
        "status": "active",
    })
    print(f"Plot B created: {plot_b['id']}")

    print("\nFarm setup complete!")
    print(f"  Location: {location['id']}")
    print(f"  Farm:     {farm['id']}")
    print(f"  Plot A:   {plot_a['id']}")
    print(f"  Plot B:   {plot_b['id']}")


if __name__ == "__main__":
    main()
