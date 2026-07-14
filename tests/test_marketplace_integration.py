"""Integration tests for services.analytics.marketplace against the real schema.

These exercise the actual SQL (canonical market_* / buyer_profile /
price_observation / market_alert / shipment tables) so the module cannot
regress to the old marketplace_* names. They skip when no database is
reachable, matching the repo's offline-test convention.
"""

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import marketplace as mp


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _seed(conn):
    """Find an existing location + crop name to attach test rows to."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        loc = cur.fetchone()
        cur.execute("SELECT name FROM crop ORDER BY name LIMIT 1")
        crop = cur.fetchone()
    if not loc or not crop:
        pytest.skip("no location/crop rows available")
    return str(loc[0]), crop[0]


def test_full_roundtrip():
    conn = _db()
    loc, crop = _seed(conn)
    created = []
    try:
        listing = mp.create_listing(conn, loc, crop, 500.0, unit="kg",
                                   price_per_unit=0.5, quality_grade="A")
        assert listing["status"] == "published"
        assert listing["crop_name"] == crop
        listing_id = listing["listing_id"]
        created.append(("market_listing", listing_id))

        active = mp.list_active_listings(conn, loc, crop)
        assert active["total"] >= 1
        assert any(l["crop_name"] == crop for l in active["listings"])

        price = mp.record_price(conn, crop, "Test Market", 0.55,
                                quality_grade="A", unit="kg", currency="USD")
        assert price["crop_name"] == crop
        created.append(("price_observation", price["price_id"]))

        trends = mp.get_price_trends(conn, crop, days=30)
        assert trends["data_points"] >= 1

        buyer = mp.create_buyer_profile(conn, "Test Buyer", "individual",
                                         location="Testville")
        buyer_id = buyer["buyer_id"]
        created.append(("buyer_profile", buyer_id))

        order = mp.create_order(conn, listing_id, buyer_id, 200.0,
                              offered_price=0.5)
        assert order["status"] == "pending"
        order_id = order["order_id"]
        created.append(("market_order", order_id))

        overview = mp.get_market_overview(conn, loc)
        assert overview["active_listings"] >= 1
        assert any(c["crop_name"] == crop for c in overview["listings_by_crop"])

        alert = mp.create_price_alert(conn, loc, crop, 0.7, direction="above")
        assert alert["crop_name"] == crop
        created.append(("market_alert", alert["alert_id"]))

        ship = mp.track_shipment(conn, order_id, location="Testville",
                                 temperature=12.0, humidity=60.0, carrier="Test Co")
        assert ship["order_id"] == order_id
        created.append(("shipment", ship["tracking_id"]))

        evaluated = mp.evaluate_listing(conn, listing_id)
        assert "evaluation" in evaluated
        assert "overall_score" in evaluated["evaluation"]
    except psycopg2.ProgrammingError:
        pytest.skip("marketplace tables not present (migration not applied)")
    finally:
        for table, pk in reversed(created):
            try:
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {table} WHERE id = %s", (pk,))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.close()
