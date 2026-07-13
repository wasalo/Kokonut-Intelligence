#!/usr/bin/env python3
"""
Tests for Mobile / Offline Data Collection
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.analytics.mobile_offline import (
    register_device,
    list_devices,
    queue_collection,
    get_pending_collections,
    sync_collections,
    resolve_conflict,
    get_sync_status,
    _format_status,
    _format_devices,
)


class TestDeviceRegistration(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("dev-001",)
        self.mock_cursor.description = [("id",)]

    def test_register_new_device(self):
        result = register_device(self.conn, "phone-001", "Field Phone", user_id="worker1")
        self.assertEqual(result["device_id"], "phone-001")
        self.assertEqual(result["status"], "registered")

    def test_register_with_location(self):
        result = register_device(self.conn, "phone-002", location_id="loc-001")
        self.assertEqual(result["device_id"], "phone-002")

    def test_register_upsert(self):
        result = register_device(self.conn, "phone-001", "Updated Name")
        self.assertEqual(result["device_id"], "phone-001")


class TestDeviceListing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        result = list_devices(self.conn)
        self.assertEqual(result, [])

    def test_list_with_devices(self):
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchall.return_value = [
            ("phone-001", "Field Phone", "phone", "worker1", "active", now, now, "1.0.0", 0),
        ]
        self.mock_cursor.description = [
            ("device_id",), ("device_name",), ("device_type",), ("user_id",), ("status",),
            ("last_sync_at",), ("last_seen_at",), ("app_version",), ("pending_count",),
        ]
        result = list_devices(self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device_id"], "phone-001")


class TestOfflineQueue(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("col-001",)
        self.mock_cursor.description = [("id",)]

    def test_queue_collection(self):
        result = queue_collection(
            self.conn, "phone-001", "soil_reading",
            {"moisture": 35.0, "temperature": 22.0},
            latitude=1.5, longitude=32.5,
        )
        self.assertIn("collection_id", result)
        self.assertEqual(result["sync_status"], "pending")

    def test_queue_duplicate_client_id(self):
        self.mock_cursor.fetchone.return_value = ("existing-id",)
        result = queue_collection(
            self.conn, "phone-001", "soil_reading",
            {"moisture": 35.0},
            client_id="client-001",
        )
        self.assertEqual(result["sync_status"], "duplicate")

    def test_get_pending_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        result = get_pending_collections(self.conn, "phone-001")
        self.assertEqual(result, [])

    def test_get_pending_with_data(self):
        self.mock_cursor.fetchall.return_value = [
            ("col-001", "phone-001", "soil_reading", {"moisture": 35}, 1.5, 32.5, datetime.now(timezone.utc), "c-001", 0, False),
        ]
        self.mock_cursor.description = [
            ("id",), ("device_id",), ("collection_type",), ("payload",),
            ("latitude",), ("longitude",), ("collected_at",), ("client_id",),
            ("server_version",), ("conflict_flag",),
        ]
        result = get_pending_collections(self.conn, "phone-001")
        self.assertEqual(len(result), 1)


class TestSync(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_sync_empty_queue(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [
            ("id",), ("collection_type",), ("payload",), ("client_id",),
            ("server_version",), ("collected_at",),
        ]
        result = sync_collections(self.conn, "phone-001")
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["status"], "completed")

    def test_sync_with_pending(self):
        self.mock_cursor.fetchall.return_value = [
            ("col-001", "soil_reading", {"moisture": 35}, None, 0, datetime.now(timezone.utc)),
            ("col-002", "weather", {"temp": 25}, None, 0, datetime.now(timezone.utc)),
        ]
        self.mock_cursor.description = [
            ("id",), ("collection_type",), ("payload",), ("client_id",),
            ("server_version",), ("collected_at",),
        ]
        result = sync_collections(self.conn, "phone-001")
        self.assertEqual(result["synced"], 2)
        self.assertEqual(result["conflicts"], 0)

    def test_resolve_conflict(self):
        self.mock_cursor.fetchone.return_value = ("col-001", "conflict", True)
        self.mock_cursor.description = [("id",), ("sync_status",), ("conflict_flag",)]
        result = resolve_conflict(self.conn, "col-001", "keep_server", "admin")
        self.assertEqual(result["status"], "resolved")

    def test_resolve_no_conflict(self):
        self.mock_cursor.fetchone.return_value = ("col-001", "synced", False)
        self.mock_cursor.description = [("id",), ("sync_status",), ("conflict_flag",)]
        result = resolve_conflict(self.conn, "col-001", "keep_server")
        self.assertIn("error", result)


class TestSyncStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_status(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.side_effect = [(0,), (None,)]
        result = get_sync_status(self.conn)
        self.assertEqual(result["total_collections"], 0)
        self.assertEqual(result["active_devices"], 0)

    def test_status_with_data(self):
        self.mock_cursor.fetchall.return_value = [("synced", 100), ("pending", 5)]
        self.mock_cursor.fetchone.side_effect = [(3,), (150.5,)]
        result = get_sync_status(self.conn)
        self.assertEqual(result["total_collections"], 105)
        self.assertEqual(result["active_devices"], 3)
        self.assertEqual(result["avg_sync_time_ms"], 150.5)


class TestFormatting(unittest.TestCase):

    def test_format_status(self):
        result = _format_status({
            "active_devices": 5,
            "total_collections": 100,
            "by_status": {"synced": 90, "pending": 10},
            "avg_sync_time_ms": 125.3,
        })
        self.assertIn("5 active devices", result)
        self.assertIn("synced: 90", result)

    def test_format_devices_empty(self):
        result = _format_devices([])
        self.assertEqual(result, "No devices registered.")

    def test_format_devices(self):
        result = _format_devices([
            {"device_id": "phone-001", "device_type": "phone", "pending_count": 0},
        ])
        self.assertIn("phone-001", result)


if __name__ == "__main__":
    unittest.main()
