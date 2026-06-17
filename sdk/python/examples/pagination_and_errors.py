"""
Pagination and Error Handling Examples

Demonstrates cursor-based pagination, offset pagination,
and error handling patterns with the Kokonut Python SDK.

Usage:
    export KOKONUT_API_URL=http://localhost:8055
    export KOKONUT_EMAIL=field@kokonut.local
    export KOKONUT_PASSWORD=field1234
    python sdk/python/examples/pagination_and_errors.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kokonut import KokonutClient, ListOptions
from kokonut.client import (
    KokonutError,
    AuthenticationError,
    NotFoundError,
    PermissionError,
    ValidationError,
)


def main():
    client = KokonutClient(os.environ.get("KOKONUT_API_URL", "http://localhost:8055"))

    # --- Authentication with error handling ---
    email = os.environ.get("KOKONUT_EMAIL", "field@kokonut.local")
    password = os.environ.get("KOKONUT_PASSWORD", "field1234")

    try:
        client.login(email, password)
        print(f"Logged in as {email}")
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
        print("Check your email and password.")
        return
    except KokonutError as e:
        print(f"Login error: {e}")
        return

    # --- Page-based pagination ---
    print("\n--- Page-based Pagination (Locations) ---")
    page = 1
    page_size = 5
    all_locations = []

    while True:
        try:
            locations = client.locations.list(
                ListOptions(
                    page=page,
                    limit=page_size,
                    sort=["name"],
                    meta="total_count",
                )
            )

            if not locations:
                break

            all_locations.extend(locations)
            print(f"  Page {page}: {len(locations)} locations")

            if len(locations) < page_size:
                break
            page += 1

        except PermissionError as e:
            print(f"Permission denied on page {page}: {e}")
            break
        except KokonutError as e:
            print(f"Error fetching page {page}: {e}")
            break

    print(f"  Total: {len(all_locations)} locations")

    # --- Offset-based pagination (harvest events) ---
    print("\n--- Offset-based Pagination (Harvest Events) ---")
    offset = 0
    limit = 10
    total_fetched = 0

    while True:
        try:
            events = client.harvest_events.list(
                ListOptions(
                    offset=offset,
                    limit=limit,
                    sort=["-harvest_date"],
                )
            )

            if not events:
                break

            for event in events:
                total_fetched += 1
                print(f"  {event['harvest_date']}: {event['quantity']} {event['unit']}")

            if len(events) < limit:
                break
            offset += limit

        except ValidationError as e:
            print(f"Validation error: {e}")
            break
        except KokonutError as e:
            print(f"Error: {e}")
            break

    print(f"  Total fetched: {total_fetched}")

    # --- Filter with error handling ---
    print("\n--- Filtered Query (Sales with payment_status=pending) ---")
    try:
        pending_sales = client.sales_events.list(
            ListOptions(
                filter={"payment_status": {"_eq": "pending"}},
                sort=["-sale_date"],
                limit=5,
            )
        )
        for sale in pending_sales:
            print(f"  {sale['sale_date']}: ${sale['total_amount']} ({sale['payment_status']})")
    except NotFoundError:
        print("  No pending sales found.")
    except PermissionError as e:
        print(f"  Cannot access sales: {e}")
    except KokonutError as e:
        print(f"  Error: {e}")

    # --- Create with validation error handling ---
    print("\n--- Create with Error Handling ---")
    try:
        new_location = client.locations.create({
            "name": "Test Pagination Farm",
            "slug": "test-pagination-farm",
            "country": "Costa Rica",
            "status": "active",
        })
        print(f"  Created: {new_location['name']} ({new_location['id']})")

        # Try creating a duplicate (should fail gracefully)
        try:
            client.locations.create({
                "name": "Test Pagination Farm",
                "slug": "test-pagination-farm",  # duplicate slug
                "country": "Costa Rica",
                "status": "active",
            })
        except ValidationError as e:
            print(f"  Duplicate slug caught: {e}")
        except KokonutError as e:
            print(f"  Duplicate slug error: {e}")

    except ValidationError as e:
        print(f"  Validation error: {e}")
    except PermissionError as e:
        print(f"  Permission denied: {e}")
    except KokonutError as e:
        print(f"  Error: {e}")

    # --- Generic error handler ---
    print("\n--- Generic Error Handling Pattern ---")
    try:
        locations = client.locations.list(ListOptions(limit=3))
        print(f"  Fetched {len(locations)} locations")
    except AuthenticationError:
        print("  Session expired. Re-login required.")
    except PermissionError:
        print("  Insufficient permissions for this operation.")
    except NotFoundError:
        print("  Resource not found.")
    except ValidationError as e:
        print(f"  Invalid request: {e}")
    except KokonutError as e:
        print(f"  API error: {e}")
    except Exception as e:
        print(f"  Unexpected error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
