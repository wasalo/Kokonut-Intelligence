"""Fail-closed compatibility tests for the retired mobile-offline CLI."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.analytics import mobile_offline


class TestLegacyMobileOfflineServiceBoundary(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()

    def assert_operation_denied(self, operation, *args, **kwargs):
        with self.assertRaisesRegex(RuntimeError, "authenticated tenant identity"):
            operation(self.connection, *args, **kwargs)
        self.assertEqual(self.connection.mock_calls, [])

    def test_registration_denied_before_database_access(self):
        self.assert_operation_denied(
            mobile_offline.register_device, "phone-001", "Field Phone"
        )

    def test_device_inventory_denied_before_database_access(self):
        self.assert_operation_denied(mobile_offline.list_devices)

    def test_legacy_collection_write_denied_before_database_access(self):
        self.assert_operation_denied(
            mobile_offline.queue_collection,
            "phone-001",
            "soil_reading",
            {"moisture": 35.0},
        )

    def test_pending_collection_read_denied_before_database_access(self):
        self.assert_operation_denied(
            mobile_offline.get_pending_collections, "phone-001"
        )

    def test_legacy_sync_denied_before_database_access(self):
        self.assert_operation_denied(mobile_offline.sync_collections, "phone-001")

    def test_conflict_write_denied_before_database_access(self):
        self.assert_operation_denied(
            mobile_offline.resolve_conflict, "collection-001"
        )

    def test_cross_tenant_status_denied_before_database_access(self):
        self.assert_operation_denied(mobile_offline.get_sync_status)


class TestLegacyMobileOfflineCLI(unittest.TestCase):
    def test_historic_commands_fail_without_opening_database(self):
        command_arguments = {
            "register": ["--device-id", "phone-001"],
            "queue": [
                "--device-id",
                "phone-001",
                "--type",
                "soil_reading",
            ],
            "sync": ["--device-id", "phone-001"],
            "status": [],
            "devices": [],
        }

        for command, arguments in command_arguments.items():
            with self.subTest(command=command):
                with patch.object(mobile_offline.cli, "_connection_factory") as factory:
                    with self.assertRaisesRegex(
                        RuntimeError, "consent-aware Field Collector"
                    ):
                        mobile_offline.cli.main([command, *arguments])
                    factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
