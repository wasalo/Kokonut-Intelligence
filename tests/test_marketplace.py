#!/usr/bin/env python3
"""
Tests for Digital Marketplace
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date, datetime, timezone, timedelta

from services.analytics.marketplace import (
    create_listing,
    update_listing,
    get_listing,
    list_active_listings,
    create_buyer_profile,
    record_price,
    get_price_trends,
    create_order,
    update_order_status,
    track_shipment,
    get_market_overview,
    create_price_alert,
    evaluate_listing,
)


class TestCreateListing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("listing-001",)

    def test_create_listing_returns_listing_id(self):
        result = create_listing(
            self.conn, "loc-001", "maize", 500, unit="kg",
            price_per_unit=0.50, quality_grade="A",
        )
        self.assertIn("listing_id", result)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["quantity"], 500)
        self.assertEqual(result["unit"], "kg")
        self.assertEqual(result["price_per_unit"], 0.50)
        self.assertEqual(result["quality_grade"], "A")
        self.assertEqual(result["status"], "active")

    def test_create_listing_calls_insert(self):
        create_listing(self.conn, "loc-001", "maize", 500)
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()

    def test_create_listing_with_harvest_date(self):
        result = create_listing(
            self.conn, "loc-001", "maize", 500,
            harvest_date=date(2026, 7, 10),
        )
        self.assertEqual(result["harvest_date"], "2026-07-10")

    def test_create_listing_closes_cursor(self):
        create_listing(self.conn, "loc-001", "maize", 500)
        self.mock_cursor.close.assert_called_once()


class TestUpdateListing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("listing-001",)

    def test_update_listing_modifies_fields(self):
        result = update_listing(
            self.conn, "listing-001", {"price_per_unit": 0.75, "quantity": 300},
        )
        self.assertEqual(result["listing_id"], "listing-001")
        self.assertIn("price_per_unit", result["updated_fields"])
        self.assertIn("quantity", result["updated_fields"])

    def test_update_listing_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = update_listing(self.conn, "bad-id", {"status": "sold"})
        self.assertIn("error", result)

    def test_update_listing_no_valid_fields(self):
        result = update_listing(self.conn, "listing-001", {"invalid_field": "value"})
        self.assertIn("error", result)


class TestGetListing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("crop_name",), ("quantity",),
            ("unit",), ("price_per_unit",), ("quality_grade",),
            ("harvest_date",), ("description",), ("images",),
            ("status",), ("metadata",), ("created_at",), ("updated_at",),
        ]
        self.mock_cursor.fetchone.return_value = (
            "listing-001", "loc-001", "maize", 500, "kg", 0.50, "A",
            date(2026, 7, 10), "Fresh maize", "[]", "active", "{}",
            datetime(2026, 7, 10, tzinfo=timezone.utc), None,
        )

    def test_get_listing_returns_listing_details(self):
        result = get_listing(self.conn, "listing-001")
        self.assertEqual(result["id"], "listing-001")
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["quantity"], 500)
        self.assertEqual(result["harvest_date"], "2026-07-10")

    def test_get_listing_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_listing(self.conn, "bad-id")
        self.assertIn("error", result)


class TestListActiveListings(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("crop_name",), ("quantity",),
            ("unit",), ("price_per_unit",), ("quality_grade",),
            ("harvest_date",), ("created_at",),
        ]

    def test_list_active_listings_filters_correctly(self):
        self.mock_cursor.fetchall.return_value = [
            ("listing-001", "loc-001", "maize", 500, "kg", 0.50, "A",
             date(2026, 7, 10), datetime(2026, 7, 10, tzinfo=timezone.utc)),
        ]
        self.mock_cursor.fetchone.return_value = (1,)
        result = list_active_listings(self.conn, location_id="loc-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["listings"]), 1)
        self.assertEqual(result["listings"][0]["crop_name"], "maize")

    def test_list_active_listings_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0,)
        result = list_active_listings(self.conn, location_id="loc-999")
        self.assertEqual(result["total"], 0)
        self.assertEqual(len(result["listings"]), 0)


class TestCreateBuyerProfile(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("buyer-001",)

    def test_create_buyer_profile_returns_buyer_id(self):
        result = create_buyer_profile(
            self.conn, "Jane Smith", buyer_type="cooperative",
        )
        self.assertIn("buyer_id", result)
        self.assertEqual(result["name"], "Jane Smith")
        self.assertEqual(result["buyer_type"], "cooperative")
        self.assertEqual(result["status"], "active")

    def test_create_buyer_profile_completes(self):
        create_buyer_profile(self.conn, "Jane Smith")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestRecordPrice(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("price-001",)

    def test_record_price_records_price(self):
        result = record_price(
            self.conn, "maize", "Adelphi Coop", 0.55, quality_grade="A",
        )
        self.assertIn("price_id", result)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["market_name"], "Adelphi Coop")
        self.assertEqual(result["price"], 0.55)
        self.assertEqual(result["quality_grade"], "A")

    def test_record_price_completes(self):
        record_price(self.conn, "maize", "Market", 0.55)
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetPriceTrends(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("price",), ("quality_grade",), ("market_name",), ("observed_at",),
        ]

    def test_get_price_trends_returns_history(self):
        self.mock_cursor.fetchall.return_value = [
            (0.50, "A", "Market A", datetime(2026, 6, 1, tzinfo=timezone.utc)),
            (0.55, "A", "Market A", datetime(2026, 6, 15, tzinfo=timezone.utc)),
            (0.60, "A", "Market A", datetime(2026, 7, 1, tzinfo=timezone.utc)),
        ]
        result = get_price_trends(self.conn, "maize", days=30)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["data_points"], 3)
        self.assertIn("avg_price", result)
        self.assertIn("trend", result)

    def test_get_price_trends_no_data(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_price_trends(self.conn, "maize", days=30)
        self.assertEqual(result["data_points"], 0)
        self.assertEqual(result["trend"], "no_data")


class TestCreateOrder(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (0.50,),
            ("order-001",),
        ]

    def test_create_order_creates_order(self):
        result = create_order(
            self.conn, "listing-001", "buyer-001", 200,
        )
        self.assertIn("order_id", result)
        self.assertEqual(result["quantity"], 200)
        self.assertEqual(result["offered_price"], 0.50)
        self.assertEqual(result["total_amount"], 100.0)
        self.assertEqual(result["status"], "pending")

    def test_create_order_with_offered_price(self):
        self.mock_cursor.fetchone.return_value = ("order-002",)
        result = create_order(
            self.conn, "listing-001", "buyer-001", 200, offered_price=0.60,
        )
        self.assertEqual(result["offered_price"], 0.60)
        self.assertEqual(result["total_amount"], 120.0)


class TestUpdateOrderStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("order-001",)

    def test_update_order_status_changes_status(self):
        result = update_order_status(
            self.conn, "order-001", "confirmed",
        )
        self.assertEqual(result["order_id"], "order-001")
        self.assertEqual(result["status"], "confirmed")

    def test_update_order_status_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = update_order_status(self.conn, "bad-id", "shipped")
        self.assertIn("error", result)


class TestTrackShipment(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("track-001",)

    def test_track_shipment_records_tracking(self):
        result = track_shipment(
            self.conn, "order-001", location="Nairobi Hub",
            temperature=4.2, humidity=65.0, carrier="DHL",
        )
        self.assertIn("tracking_id", result)
        self.assertEqual(result["order_id"], "order-001")
        self.assertEqual(result["location"], "Nairobi Hub")
        self.assertEqual(result["temperature"], 4.2)
        self.assertEqual(result["carrier"], "DHL")

    def test_track_shipment_completes(self):
        track_shipment(self.conn, "order-001")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetMarketOverview(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

        # get_market_overview makes 1 fetchone + 3 fetchall calls
        # Use execute.side_effect to update description for each query
        self.descs = [
            None,  # listing count (fetchone, no description needed)
            [("crop_name",), ("count",), ("total_qty",), ("avg_price",)],
            [("crop_name",), ("avg_price",), ("min_price",), ("max_price",), ("observations",)],
            [("status",), ("count",)],
        ]
        self.desc_idx = [0]
        def update_desc(*args, **kwargs):
            if self.desc_idx[0] < len(self.descs) and self.descs[self.desc_idx[0]] is not None:
                self.mock_cursor.description = self.descs[self.desc_idx[0]]
            self.desc_idx[0] += 1
        self.mock_cursor.execute.side_effect = update_desc

        self.mock_cursor.fetchone.return_value = (5, 2500.0)
        self.mock_cursor.fetchall.side_effect = [
            [("maize", 3, 1500.0, 0.55)],
            [("maize", 0.55, 0.50, 0.60, 10)],
            [("pending", 2), ("confirmed", 3)],
        ]

    def test_get_market_overview_aggregates_data(self):
        result = get_market_overview(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["active_listings"], 5)
        self.assertEqual(result["total_quantity_listed"], 2500.0)
        self.assertEqual(len(result["listings_by_crop"]), 1)
        self.assertEqual(len(result["recent_prices_30d"]), 1)


class TestCreatePriceAlert(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("alert-001",)

    def test_create_price_alert_creates_alert(self):
        result = create_price_alert(
            self.conn, "loc-001", "maize", 0.70, direction="above",
        )
        self.assertIn("alert_id", result)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["threshold"], 0.70)
        self.assertEqual(result["direction"], "above")
        self.assertEqual(result["status"], "active")


class TestEvaluateListing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

        # evaluate_listing makes 2 fetchone + 1 fetchall calls
        self.descs = [
            [("id",), ("crop_name",), ("quantity",), ("unit",),
             ("price_per_unit",), ("quality_grade",), ("harvest_date",),
             ("location_id",)],
            [("price",), ("quality_grade",)],
            None,  # yield fetchone
        ]
        self.desc_idx = [0]
        def update_desc(*args, **kwargs):
            if self.desc_idx[0] < len(self.descs) and self.descs[self.desc_idx[0]] is not None:
                self.mock_cursor.description = self.descs[self.desc_idx[0]]
            self.desc_idx[0] += 1
        self.mock_cursor.execute.side_effect = update_desc

        self.mock_cursor.fetchone.side_effect = [
            ("listing-001", "maize", 500, "kg", 0.50, "A",
             date(2026, 7, 10), "loc-001"),
            (2500.0, 300.0),
        ]
        self.mock_cursor.fetchall.return_value = [
            (0.50, "A"), (0.55, "A"), (0.60, "A"),
        ]

    def test_evaluate_listing_returns_evaluation(self):
        result = evaluate_listing(self.conn, "listing-001")
        self.assertIn("evaluation", result)
        self.assertIn("overall_score", result["evaluation"])
        self.assertIn("recommendation", result)

    def test_evaluate_listing_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        result = evaluate_listing(self.conn, "bad-id")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
