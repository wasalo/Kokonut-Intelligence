"""Example: Batch upload sensor readings and expense events.

Usage:
    KOKONUT_TOKEN=... python examples/batch_upload.py
"""

from __future__ import annotations

import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kokonut import KokonutClient, ListOptions

BASE_URL = os.environ.get("KOKONUT_BASE_URL", "http://localhost:8055")
TOKEN = os.environ.get("KOKONUT_TOKEN")


def generate_sensor_readings(
    location_id: str,
    plot_id: str,
    sensor_id: str,
    hours: int = 24,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    readings = []
    for i in range(hours):
        ts = now - timedelta(hours=hours - 1 - i)
        value = 22.0 + random.random() * 3.0
        # Inject an anomaly at hour 20
        if i == 20:
            value += 15.0
        readings.append({
            "location_id": location_id,
            "plot_id": plot_id,
            "sensor_id": sensor_id,
            "sensor_type": "soil_temp",
            "reading_date": ts.strftime("%Y-%m-%d"),
            "reading_time": ts.strftime("%H:%M:%S"),
            "value": round(value, 2),
            "unit": "°C",
            "quality": "good",
        })
    return readings


def generate_expenses(
    location_id: str,
    crop_cycle_id: str,
    plot_id: str,
) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "location_id": location_id,
            "plot_id": plot_id,
            "crop_cycle_id": crop_cycle_id,
            "expense_date": today,
            "category": "seed",
            "subcategory": "coffee_seedlings",
            "description": "Castillo variety seedlings - 2000 units",
            "vendor": "Vivero La Esperanza",
            "amount": 340.00,
            "currency": "USD",
            "is_capex": False,
            "allocation_method": "direct",
            "status": "verified",
        },
        {
            "location_id": location_id,
            "plot_id": plot_id,
            "crop_cycle_id": crop_cycle_id,
            "expense_date": today,
            "category": "fertilizer",
            "description": "Organic compost - 5 tons",
            "vendor": "Agro Organicos SA",
            "amount": 1200.00,
            "currency": "USD",
            "is_capex": False,
            "allocation_method": "proportional",
            "status": "verified",
        },
        {
            "location_id": location_id,
            "plot_id": plot_id,
            "crop_cycle_id": crop_cycle_id,
            "expense_date": today,
            "category": "labor",
            "description": "Harvest crew - 8 workers x 1 day",
            "vendor": "Cooperativa Local",
            "amount": 640.00,
            "currency": "USD",
            "is_capex": False,
            "allocation_method": "direct",
            "status": "submitted",
        },
        {
            "location_id": location_id,
            "plot_id": plot_id,
            "crop_cycle_id": crop_cycle_id,
            "expense_date": today,
            "category": "equipment",
            "description": "Drip irrigation repair parts",
            "vendor": "AgriParts Ltd",
            "amount": 890.00,
            "currency": "USD",
            "is_capex": True,
            "allocation_method": "equal",
            "status": "verified",
        },
    ]


def detect_anomalies(readings: list[dict], window: int = 5) -> list[bool]:
    flags = []
    for i, r in enumerate(readings):
        if i < window:
            flags.append(False)
            continue
        window_vals = [readings[j]["value"] for j in range(i - window, i)]
        mean = sum(window_vals) / len(window_vals)
        std = (sum((v - mean) ** 2 for v in window_vals) / len(window_vals)) ** 0.5
        z = abs(r["value"] - mean) / std if std > 0 else 0
        flags.append(z > 2.5)
    return flags


def main() -> None:
    client = KokonutClient(BASE_URL, token=TOKEN)

    if not TOKEN:
        client.login("admin@example.com", "password123")

    # --- Sensor readings ---
    sensor_id = "sensor-plot-a-001"
    readings = generate_sensor_readings(
        location_id="",
        plot_id="",
        sensor_id=sensor_id,
    )

    # Upload raw readings (location_id/plot_id would be real UUIDs)
    created = client.sensor_readings.create_many(readings)
    print(f"Uploaded {len(created)} sensor readings")

    # Flag anomalies
    flags = detect_anomalies(readings)
    anomaly_count = sum(flags)
    print(f"Detected {anomaly_count} anomalies in batch")

    if anomaly_count > 0:
        for i, (r, is_anom) in enumerate(zip(created, flags)):
            if is_anom:
                print(f"  Reading {i}: {r.get('reading_date')} {r.get('reading_time')} "
                      f"= {r['value']}{r['unit']}")

    # --- Expense events ---
    expenses = generate_expenses(
        location_id="",
        crop_cycle_id="",
        plot_id="",
    )
    created_expenses = client.expense_events.create_many(expenses)
    print(f"\nUploaded {len(created_expenses)} expense events")

    total = sum(e.get("amount", 0) or 0 for e in created_expenses)
    capex = sum(e.get("amount", 0) or 0 for e in created_expenses if e.get("is_capex"))
    opex = total - capex
    print(f"  Total: ${total:,.2f}  (OpEx: ${opex:,.2f}, CapEx: ${capex:,.2f})")

    pending = [e for e in created_expenses if e.get("status") == "submitted"]
    print(f"  Pending verification: {len(pending)}")


if __name__ == "__main__":
    main()
