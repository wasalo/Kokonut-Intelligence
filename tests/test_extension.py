#!/usr/bin/env python3
"""
Tests for Digital Extension Services
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.analytics.extension import (
    create_module,
    list_modules,
    enroll_farmer,
    update_progress,
    get_farmer_progress,
    get_module_stats,
    create_peer_group,
    add_peer_member,
    get_peer_groups,
    deliver_content,
    get_delivery_stats,
    record_assessment,
    get_extension_effectiveness,
    recommend_modules,
)


class TestCreateModule(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("mod-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_module_returns_module_id(self):
        result = create_module(
            self.conn, "Soil Health 101", "soil_health", "guide",
        )
        self.assertIn("module_id", result)
        self.assertEqual(result["title"], "Soil Health 101")
        self.assertEqual(result["category"], "soil_health")
        self.assertEqual(result["content_type"], "guide")
        self.assertEqual(result["status"], "draft")

    def test_create_module_calls_insert(self):
        create_module(self.conn, "Module A", "water_management", "video")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()

    def test_create_module_with_options(self):
        result = create_module(
            self.conn, "Module B", "pest_control", "quiz",
            difficulty="advanced", duration_min=45, language="es",
        )
        self.assertEqual(result["difficulty"], "advanced")


class TestListModules(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_modules_filters(self):
        self.mock_cursor.description = [
            ("id",), ("module_name",), ("description",), ("category",),
            ("difficulty",), ("content_type",), ("content_url",),
            ("duration_minutes",), ("language",), ("tags",),
            ("status",), ("created_at",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("mod-001", "Soil 101", "Basic soil", "soil_health", "beginner", "guide", None, 30, "en", [], "active", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        result = list_modules(self.conn, category="soil_health", difficulty="beginner")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "soil_health")

    def test_list_modules_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("id",), ("module_name",), ("description",), ("category",), ("difficulty",), ("content_type",), ("content_url",), ("duration_minutes",), ("language",), ("tags",), ("status",), ("created_at",)]
        result = list_modules(self.conn)
        self.assertEqual(len(result), 0)


class TestEnrollFarmer(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001",),  # location lookup
            None,  # no existing enrollment
            ("prog-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]

    def test_enroll_farmer_returns_progress_id(self):
        result = enroll_farmer(self.conn, "farmer-001", "mod-001")
        self.assertIn("progress_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["module_id"], "mod-001")
        self.assertEqual(result["status"], "in_progress")

    def test_enroll_farmer_duplicate_raises(self):
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001",),
            ("existing-prog",),
        ]
        with self.assertRaises(ValueError):
            enroll_farmer(self.conn, "farmer-001", "mod-001")


class TestUpdateProgress(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_update_progress_returns_updated(self):
        self.mock_cursor.fetchone.return_value = (
            "prog-001", "mod-001", "farmer-001", 100.0, 85.0,
            "completed", datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        result = update_progress(self.conn, "prog-001", status="completed", score=85.0)
        self.assertEqual(result["progress_id"], "prog-001")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 85.0)

    def test_update_progress_not_found_raises(self):
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            update_progress(self.conn, "prog-999", status="completed")


class TestGetFarmerProgress(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_farmer_progress_returns_data(self):
        self.mock_cursor.description = [
            ("id",), ("module_id",), ("module_name",), ("category",),
            ("difficulty",), ("progress_pct",), ("score",),
            ("time_spent_min",), ("attempts",), ("started_at",),
            ("completed_at",), ("status",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("prog-001", "mod-001", "Soil 101", "soil_health", "beginner", 100.0, 85.0, 30, 1, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "completed"),
        ]
        result = get_farmer_progress(self.conn, "farmer-001")
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["total_enrolled"], 1)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["avg_score"], 85.0)

    def test_farmer_progress_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("id",), ("module_id",), ("module_name",), ("category",), ("difficulty",), ("progress_pct",), ("score",), ("time_spent_min",), ("attempts",), ("started_at",), ("completed_at",), ("status",)]
        result = get_farmer_progress(self.conn, "farmer-999")
        self.assertEqual(result["total_enrolled"], 0)
        self.assertIsNone(result["avg_score"])


class TestGetModuleStats(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_module_stats_returns_stats(self):
        self.mock_cursor.fetchone.side_effect = [
            (20, 12, 6, 2, 82.5, 25.0, 65.0, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 6, 1, tzinfo=timezone.utc)),
            ("Soil 101", "soil_health", "beginner"),
        ]
        result = get_module_stats(self.conn, "mod-001")
        self.assertEqual(result["module_id"], "mod-001")
        self.assertEqual(result["total_enrolled"], 20)
        self.assertEqual(result["completed"], 12)
        self.assertEqual(result["completion_rate_pct"], 60.0)


class TestCreatePeerGroup(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("grp-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_peer_group_returns_group_id(self):
        result = create_peer_group(
            self.conn, "Adelphi FFS", "soil_health",
            location_id="loc-001",
        )
        self.assertIn("group_id", result)
        self.assertEqual(result["name"], "Adelphi FFS")
        self.assertEqual(result["topic"], "soil_health")
        self.assertEqual(result["status"], "active")

    def test_create_peer_group_calls_insert(self):
        create_peer_group(self.conn, "Group A", "water")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestAddPeerMember(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_add_peer_member_returns_member_id(self):
        self.mock_cursor.fetchone.side_effect = [
            None,  # location from peer_network_member (no member yet)
            ("loc-001",),  # location from peer_network
            None,  # no duplicate member
            ("mem-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = add_peer_member(
            self.conn, "grp-001", "farmer-001", role="member",
        )
        self.assertIn("member_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["role"], "member")

    def test_add_peer_member_duplicate_raises(self):
        self.mock_cursor.fetchone.side_effect = [
            None,  # location from peer_network_member
            ("loc-001",),  # location from peer_network
            ("existing-mem",),  # duplicate found
        ]
        with self.assertRaises(ValueError):
            add_peer_member(self.conn, "grp-001", "farmer-001")


class TestGetPeerGroups(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_peer_groups_returns_groups(self):
        self.mock_cursor.description = [
            ("id",), ("network_name",), ("network_type",), ("location_id",),
            ("max_members",), ("meeting_cadence",), ("status",), ("created_at",),
            ("member_count",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("grp-001", "Adelphi FFS", "learning_group", "loc-001", 20, "weekly", "active", datetime(2026, 1, 1, tzinfo=timezone.utc), 5),
        ]
        result = get_peer_groups(self.conn, location_id="loc-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["network_name"], "Adelphi FFS")
        self.assertEqual(result[0]["member_count"], 5)


class TestDeliverContent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            None,  # location from learning_progress
            ("loc-001",),  # location from location table
            ("del-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]

    def test_deliver_content_records_delivery(self):
        result = deliver_content(
            self.conn, "farmer-001", "mod-001", "sms",
        )
        self.assertIn("delivery_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["channel"], "sms")
        self.assertEqual(result["status"], "sent")


class TestGetDeliveryStats(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_delivery_stats_returns_stats(self):
        self.mock_cursor.description = [
            ("delivery_channel",), ("total",), ("delivered",),
            ("viewed",), ("clicked",), ("failed",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("sms", 10, 8, 5, 3, 1)],
        ]
        self.mock_cursor.fetchone.return_value = (10, 8, 1, 3)
        result = get_delivery_stats(self.conn, "farmer-001")
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["total_deliveries"], 10)
        self.assertEqual(result["unique_modules"], 3)


class TestRecordAssessment(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            ("loc-001",),  # location from learning_progress
            ("assess-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]

    def test_record_assessment_returns_assessment_id(self):
        result = record_assessment(
            self.conn, "farmer-001", "mod-001", "pre_test", 60.0,
        )
        self.assertIn("assessment_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["assessment_type"], "pre_test")
        self.assertEqual(result["score"], 60.0)

    def test_record_assessment_with_max_score(self):
        result = record_assessment(
            self.conn, "farmer-001", "mod-001", "post_test", 85.0,
            max_score=100,
        )
        self.assertEqual(result["max_score"], 100)


class TestGetExtensionEffectiveness(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_effectiveness_returns_metrics(self):
        self.mock_cursor.description = [
            ("category",), ("module_name",), ("enrollments",), ("completions",),
            ("avg_score",), ("avg_time_min",), ("avg_pre_score",), ("avg_post_score",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("soil_health", "Soil 101", 10, 7, 82.5, 25, 60.0, 82.0),
        ]
        result = get_extension_effectiveness(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total_enrollments"], 10)
        self.assertEqual(result["total_completions"], 7)
        self.assertIn("modules", result)
        self.assertIn("by_category", result)


class TestRecommendModules(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_recommend_returns_recommendations(self):
        self.mock_cursor.description = [
            ("module_id",), ("status",), ("score",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("mod-001", "completed", 85.0)],  # enrolled
            [],  # recent assessments
            [("mod-001", "Soil 101", "soil_health", "beginner", []),
             ("mod-002", "Water 101", "water_management", "beginner", [])],  # all modules
        ]
        result = recommend_modules(self.conn, "farmer-001", "loc-001")
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["modules_completed"], 1)
        self.assertIn("recommendations", result)
        self.assertIsInstance(result["recommendations"], list)

    def test_recommend_no_enrollments(self):
        self.mock_cursor.description = [
            ("module_id",), ("status",), ("score",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [],  # no enrolled
            [],  # no assessments
            [("mod-001", "Soil 101", "soil_health", "beginner", [])],
        ]
        result = recommend_modules(self.conn, "farmer-001", "loc-001")
        self.assertEqual(result["modules_completed"], 0)
        self.assertGreater(len(result["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
