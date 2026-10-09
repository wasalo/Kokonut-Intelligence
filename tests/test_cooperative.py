#!/usr/bin/env python3
"""
Tests for Digital Cooperative Services
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import unittest.mock
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone

from services.analytics.cooperative import (
    create_cooperative,
    add_member,
    get_cooperative_summary,
    list_cooperatives,
    add_shared_asset,
    book_asset,
    get_asset_utilization,
    create_collective_purchase,
    add_purchase_participant,
    create_market_order,
    add_market_participant,
    get_collective_orders,
    get_member_dashboard,
)


class TestCreateCooperative(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_create_cooperative_returns_coop_id(self):
        self.mock_cursor.fetchone.side_effect = [
            ("type-001",),  # type lookup
            ("coop-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = create_cooperative(
            self.conn, "Adelphi Coop", "marketing", "loc-001",
        )
        self.assertIn("cooperative_id", result)
        self.assertEqual(result["name"], "Adelphi Coop")
        self.assertEqual(result["type"], "marketing")
        self.assertEqual(result["location_id"], "loc-001")

    def test_create_cooperative_unknown_type(self):
        self.mock_cursor.fetchone.return_value = None
        result = create_cooperative(
            self.conn, "Test Coop", "unknown_type", "loc-001",
        )
        self.assertIn("error", result)

    def test_create_cooperative_calls_commit(self):
        self.mock_cursor.fetchone.side_effect = [
            ("type-001",),
            ("coop-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        create_cooperative(self.conn, "Coop A", "marketing", "loc-001")
        self.conn.commit.assert_called_once()


class TestAddMember(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_add_member_returns_member_id(self):
        self.mock_cursor.fetchone.side_effect = [
            ("coop-001",),  # cooperative exists
            ("loc-001",),   # location lookup
            None,           # no existing member
            ("mem-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = add_member(
            self.conn, "coop-001", "farmer-001", role="member", shares=5,
        )
        self.assertIn("member_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["role"], "member")
        self.assertEqual(result["shares"], 5)

    def test_add_member_cooperative_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = add_member(self.conn, "coop-999", "farmer-001")
        self.assertEqual(result["error"], "Cooperative not found")

    def test_add_member_duplicate(self):
        self.mock_cursor.fetchone.side_effect = [
            ("coop-001",),
            ("loc-001",),
            ("existing-mem",),
        ]
        result = add_member(self.conn, "coop-001", "farmer-001")
        self.assertIn("error", result)


class TestGetCooperativeSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.now = datetime.now(timezone.utc)
        self.coop_cols = [
            ("id",), ("name",), ("type_name",), ("location_id",),
            ("governance_model",), ("description",), ("mission_statement",),
            ("membership_count",), ("total_revenue",), ("total_assets_value",),
            ("founded_date",), ("status",), ("created_at",),
        ]
        self.member_cols = [
            ("id",), ("member_name",), ("member_type",), ("role",),
            ("share_count",), ("join_date",), ("status",),
        ]
        self.asset_cols = [
            ("id",), ("name",), ("asset_type",), ("daily_rate",),
            ("status",), ("condition_rating",), ("total_bookings",),
            ("avg_utilization_pct",),
        ]
        self.purchase_cols = [
            ("id",), ("order_name",), ("input_category",),
            ("target_quantity",), ("unit",), ("negotiated_unit_price",),
            ("participant_count",), ("status",),
        ]
        self.market_cols = [
            ("id",), ("order_name",), ("crop_type",),
            ("quality_grade",), ("total_quantity",), ("unit",),
            ("target_price",), ("status",),
        ]

    def test_cooperative_summary_returns_data(self):
        type(self.mock_cursor).description = unittest.mock.PropertyMock(
            side_effect=[
                self.coop_cols,
                self.member_cols,
                self.asset_cols,
                self.purchase_cols,
                self.market_cols,
            ]
        )
        self.mock_cursor.fetchone.return_value = (
            "coop-001", "Adelphi Coop", "marketing", "loc-001",
            "one_member_one_vote", "Test desc", "Our mission",
            5, 10000.0, 5000.0, None, "active", self.now,
        )
        self.mock_cursor.fetchall.side_effect = [
            [],  # members
            [],  # assets
            [],  # purchases
            [],  # market orders
        ]
        result = get_cooperative_summary(self.conn, "coop-001")
        self.assertEqual(result["cooperative_id"], "coop-001")
        self.assertEqual(result["name"], "Adelphi Coop")
        self.assertEqual(result["membership_count"], 5)
        self.assertEqual(result["total_revenue"], 10000.0)

    def test_cooperative_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_cooperative_summary(self.conn, "coop-999")
        self.assertEqual(result["error"], "Cooperative not found")


class TestListCooperatives(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_cooperatives_returns_list(self):
        self.mock_cursor.description = [
            ("id",), ("name",), ("type_name",), ("governance_model",),
            ("membership_count",), ("total_revenue",), ("status",), ("created_at",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("coop-001", "Adelphi Coop", "marketing", "one_member_one_vote", 5, 10000.0, "active", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        result = list_cooperatives(self.conn, "loc-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Adelphi Coop")

    def test_list_cooperatives_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("id",), ("name",), ("type_name",), ("governance_model",), ("membership_count",), ("total_revenue",), ("status",), ("created_at",)]
        result = list_cooperatives(self.conn, "loc-001")
        self.assertEqual(len(result), 0)


class TestAddSharedAsset(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001",),  # cooperative location
            ("asset-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]

    def test_add_asset_returns_asset_id(self):
        result = add_shared_asset(
            self.conn, "coop-001", "Tractor", "tractor", 50.0,
        )
        self.assertIn("asset_id", result)
        self.assertEqual(result["name"], "Tractor")
        self.assertEqual(result["asset_type"], "tractor")
        self.assertEqual(result["daily_rate"], 50.0)

    def test_add_asset_cooperative_not_found(self):
        self.mock_cursor.fetchone.side_effect = [None]
        result = add_shared_asset(
            self.conn, "coop-999", "Tractor", "tractor", 50.0,
        )
        self.assertEqual(result["error"], "Cooperative not found")


class TestBookAsset(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_book_asset_returns_booking(self):
        self.mock_cursor.fetchone.side_effect = [
            None,  # no conflicting booking
            (50.0, 10.0, "coop-001"),  # asset details
            ("mem-001",),  # membership valid
            ("book-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = book_asset(
            self.conn, "asset-001", "mem-001",
            "2026-07-15T08:00", "2026-07-20T17:00",
        )
        self.assertIn("booking_id", result)
        self.assertEqual(result["asset_id"], "asset-001")
        self.assertIn("total_cost", result)

    def test_book_asset_conflict(self):
        self.mock_cursor.fetchone.return_value = ("conflict-001",)
        result = book_asset(
            self.conn, "asset-001", "mem-001",
            "2026-07-15T08:00", "2026-07-20T17:00",
        )
        self.assertIn("error", result)


class TestGetAssetUtilization(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_asset_utilization_returns_metrics(self):
        self.mock_cursor.description = [
            ("id",), ("name",), ("asset_type",), ("daily_rate",),
            ("hourly_rate",), ("total_bookings",), ("avg_utilization_pct",),
            ("condition_rating",), ("status",), ("upcoming_bookings",),
            ("hours_used_this_month",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("asset-001", "Tractor", "tractor", 50.0, 10.0, 15, 75.5, 4.5, "available", 3, 40.0),
        ]
        result = get_asset_utilization(self.conn, "coop-001")
        self.assertEqual(result["cooperative_id"], "coop-001")
        self.assertEqual(result["total_assets"], 1)
        self.assertEqual(result["total_bookings"], 15)


class TestCreateCollectivePurchase(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("purch-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_purchase_returns_purchase_id(self):
        result = create_collective_purchase(
            self.conn, "coop-001", "Bulk Seeds", "seeds",
            1000.0, "kg", 2.50,
        )
        self.assertIn("purchase_id", result)
        self.assertEqual(result["order_name"], "Bulk Seeds")
        self.assertEqual(result["input_category"], "seeds")
        self.assertEqual(result["target_quantity"], 1000.0)

    def test_create_purchase_calls_insert(self):
        create_collective_purchase(
            self.conn, "coop-001", "Fertilizer", "fertilizer",
            500.0, "kg", 3.00,
        )
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestAddPurchaseParticipant(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_add_participant_returns_participant_id(self):
        self.mock_cursor.fetchone.side_effect = [
            ("coop-001", "collecting"),  # purchase status
            ("mem-001",),  # membership valid
            None,  # no duplicate
            ("part-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = add_purchase_participant(
            self.conn, "purch-001", "mem-001", 100.0, 250.0,
        )
        self.assertIn("participant_id", result)
        self.assertEqual(result["quantity"], 100.0)
        self.assertEqual(result["commitment_amount"], 250.0)

    def test_add_participant_purchase_not_collecting(self):
        self.mock_cursor.fetchone.return_value = ("coop-001", "completed")
        result = add_purchase_participant(
            self.conn, "purch-001", "mem-001", 100.0, 250.0,
        )
        self.assertIn("error", result)


class TestCreateMarketOrder(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("order-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_market_order_returns_order_id(self):
        result = create_market_order(
            self.conn, "coop-001", "Maize Bulk", "maize",
            5000.0, "kg", 350.0, quality_grade="A",
        )
        self.assertIn("market_order_id", result)
        self.assertEqual(result["order_name"], "Maize Bulk")
        self.assertEqual(result["crop_type"], "maize")
        self.assertEqual(result["quantity"], 5000.0)
        self.assertEqual(result["quality_grade"], "A")

    def test_create_market_order_calls_insert(self):
        create_market_order(
            self.conn, "coop-001", "Beans Bulk", "beans",
            2000.0, "kg", 200.0,
        )
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestAddMarketParticipant(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_add_market_participant_returns_participant(self):
        self.mock_cursor.fetchone.side_effect = [
            ("coop-001", "collecting", 5000.0),  # order details
            ("mem-001",),  # membership valid
            None,  # no duplicate
            (0,),  # committed quantity
            ("mp-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = add_market_participant(
            self.conn, "order-001", "mem-001", 500.0,
        )
        self.assertIn("participant_id", result)
        self.assertEqual(result["quantity"], 500.0)

    def test_add_market_participant_exceeds_capacity(self):
        self.mock_cursor.fetchone.side_effect = [
            ("coop-001", "collecting", 100.0),
            ("mem-001",),
            None,
            (80,),
        ]
        result = add_market_participant(
            self.conn, "order-001", "mem-001", 50.0,
        )
        self.assertIn("error", result)


class TestGetCollectiveOrders(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_collective_orders_returns_orders(self):
        self.mock_cursor.description = [
            ("id",), ("order_name",), ("input_category",),
            ("target_quantity",), ("unit",), ("negotiated_unit_price",),
            ("participant_count",), ("status",), ("expected_delivery",),
            ("committed_quantity",), ("committed_amount",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [],  # purchases
            [],  # market orders
        ]
        result = get_collective_orders(self.conn, "coop-001")
        self.assertEqual(result["cooperative_id"], "coop-001")
        self.assertEqual(len(result["purchases"]), 0)
        self.assertEqual(len(result["market_orders"]), 0)


class TestGetMemberDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_member_dashboard_returns_data(self):
        self.mock_cursor.description = [
            ("id",), ("cooperative_id",), ("cooperative_name",),
            ("cooperative_type",), ("role",), ("share_count",),
            ("join_date",), ("status",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("mem-001", "coop-001", "Adelphi Coop", "marketing", "member", 10, date(2026, 1, 1), "active")],
            [],  # bookings
            [],  # purchases
            [],  # market participation
        ]
        result = get_member_dashboard(self.conn, "farmer-001")
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["cooperatives_count"], 1)
        self.assertEqual(result["total_shares"], 10)
        self.assertEqual(len(result["memberships"]), 1)

    def test_member_dashboard_empty(self):
        self.mock_cursor.description = [
            ("id",), ("cooperative_id",), ("cooperative_name",),
            ("cooperative_type",), ("role",), ("share_count",),
            ("join_date",), ("status",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [], [], [], [],
        ]
        result = get_member_dashboard(self.conn, "farmer-999")
        self.assertEqual(result["cooperatives_count"], 0)
        self.assertEqual(result["total_shares"], 0)


if __name__ == "__main__":
    unittest.main()
