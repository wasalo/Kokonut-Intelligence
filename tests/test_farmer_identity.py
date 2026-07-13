#!/usr/bin/env python3
"""
Tests for Farmer Identity & Access Management
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone

from services.analytics.farmer_identity import (
    create_profile,
    update_profile,
    get_profile,
    list_farmers,
    add_credential,
    verify_credential,
    get_credentials,
    create_kyc,
    verify_kyc,
    assign_role,
    check_permission,
    record_data_sharing_consent,
    register_device,
    get_access_matrix,
    get_farmer_directory,
)


class TestCreateProfile(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("farmer-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_profile_returns_farmer_id(self):
        result = create_profile(self.conn, "John", last_name="Doe")
        self.assertIn("farmer_id", result)
        self.assertEqual(result["first_name"], "John")
        self.assertEqual(result["last_name"], "Doe")
        self.assertEqual(result["status"], "active")

    def test_create_profile_with_location(self):
        result = create_profile(self.conn, "Jane", location_id="loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_create_profile_calls_insert(self):
        create_profile(self.conn, "Test")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestUpdateProfile(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_update_profile_returns_updated(self):
        self.mock_cursor.fetchone.return_value = (
            "farmer-001", datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        result = update_profile(self.conn, "farmer-001", {"last_name": "Smith"})
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertIn("last_name", result["updated_fields"])

    def test_update_profile_no_valid_fields(self):
        result = update_profile(self.conn, "farmer-001", {"invalid_field": "value"})
        self.assertEqual(result["error"], "No valid fields to update")

    def test_update_profile_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = update_profile(self.conn, "farmer-999", {"last_name": "X"})
        self.assertEqual(result["error"], "Farmer farmer-999 not found")


class TestGetProfile(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_profile_returns_profile(self):
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("first_name",), ("last_name",),
            ("date_of_birth",), ("gender",), ("phone",), ("phone_verified",),
            ("email",), ("email_verified",), ("village",), ("district",),
            ("province",), ("country",), ("postal_code",), ("farm_size_ha",),
            ("primary_crops",), ("farming_type",), ("years_farming",),
            ("national_id_type",), ("national_id_number",), ("national_id_country",),
            ("kyc_status",), ("kyc_verified_at",), ("status",), ("metadata",),
            ("created_at",), ("updated_at",),
        ]
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchone.return_value = (
            "farmer-001", "loc-001", "John", "Doe",
            date(1990, 1, 1), "male", "+1234567890", True,
            None, False, "Village A", "District B",
            "Province C", "Kenya", None, 2.5,
            ["maize"], "conventional", 5,
            "national_id", "12345", "KE",
            "verified", now, "active", {},
            now, now,
        )
        result = get_profile(self.conn, "farmer-001")
        self.assertEqual(result["id"], "farmer-001")
        self.assertEqual(result["first_name"], "John")
        self.assertEqual(result["kyc_status"], "verified")

    def test_get_profile_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_profile(self.conn, "farmer-999")
        self.assertEqual(result["error"], "Farmer farmer-999 not found")


class TestListFarmers(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_farmers_returns_list(self):
        self.mock_cursor.description = [
            ("id",), ("first_name",), ("last_name",), ("phone",),
            ("email",), ("village",), ("district",), ("farm_size_ha",),
            ("primary_crops",), ("farming_type",), ("kyc_status",),
            ("status",), ("created_at",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("farmer-001", "John", "Doe", "+1234567890", None, "Village A", "District B", 2.5, ["maize"], "conventional", "verified", "active", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        self.mock_cursor.fetchone.return_value = (1,)
        result = list_farmers(self.conn, location_id="loc-001")
        self.assertEqual(len(result["farmers"]), 1)
        self.assertEqual(result["total"], 1)

    def test_list_farmers_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0,)
        self.mock_cursor.description = [("id",), ("first_name",), ("last_name",), ("phone",), ("email",), ("village",), ("district",), ("farm_size_ha",), ("primary_crops",), ("farming_type",), ("kyc_status",), ("status",), ("created_at",)]
        result = list_farmers(self.conn)
        self.assertEqual(len(result["farmers"]), 0)


class TestAddCredential(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("cred-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_add_credential_returns_credential_id(self):
        result = add_credential(
            self.conn, "farmer-001", "organic_cert", "Organic Certificate",
        )
        self.assertIn("credential_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["credential_type"], "organic_cert")
        self.assertEqual(result["status"], "active")

    def test_add_credential_calls_insert(self):
        add_credential(self.conn, "farmer-001", "training_cert", "Training Cert")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestVerifyCredential(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_verify_credential_returns_verified(self):
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchone.return_value = (
            "cred-001", "organic_cert", "Organic Certificate", now,
        )
        result = verify_credential(self.conn, "cred-001", verified_by="admin")
        self.assertEqual(result["credential_id"], "cred-001")
        self.assertTrue(result["is_verified"])

    def test_verify_credential_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = verify_credential(self.conn, "cred-999")
        self.assertEqual(result["error"], "Credential cred-999 not found")


class TestGetCredentials(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_credentials_returns_credentials(self):
        self.mock_cursor.description = [
            ("id",), ("credential_type",), ("credential_name",),
            ("issuing_authority",), ("credential_number",), ("credential_url",),
            ("issued_date",), ("expiry_date",), ("is_verified",),
            ("verified_by",), ("verified_at",), ("evidence_urls",),
            ("status",), ("created_at",),
        ]
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchall.return_value = [
            ("cred-001", "organic_cert", "Organic Certificate",
             "KRA", "12345", None, date(2025, 1, 1), date(2027, 1, 1),
             True, "admin", now, [], "active", now),
        ]
        result = get_credentials(self.conn, "farmer-001")
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["credentials"][0]["credential_type"], "organic_cert")

    def test_get_credentials_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("id",), ("credential_type",), ("credential_name",), ("issuing_authority",), ("credential_number",), ("credential_url",), ("issued_date",), ("expiry_date",), ("is_verified",), ("verified_by",), ("verified_at",), ("evidence_urls",), ("status",), ("created_at",)]
        result = get_credentials(self.conn, "farmer-999")
        self.assertEqual(result["total"], 0)


class TestCreateKyc(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("kyc-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_create_kyc_returns_kyc_id(self):
        result = create_kyc(self.conn, "farmer-001", "national_id")
        self.assertIn("kyc_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["verification_method"], "national_id")
        self.assertEqual(result["verification_status"], "pending")

    def test_create_kyc_calls_update_profile(self):
        create_kyc(self.conn, "farmer-001", "passport")
        self.assertEqual(self.mock_cursor.execute.call_count, 2)


class TestVerifyKyc(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_verify_kyc_approved(self):
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchone.side_effect = [
            ("kyc-001", "farmer-001", "national_id", "approved", now),  # update result
            None,  # profile update
        ]
        result = verify_kyc(self.conn, "kyc-001", "approved", verified_by="admin")
        self.assertEqual(result["kyc_id"], "kyc-001")
        self.assertEqual(result["verification_status"], "approved")

    def test_verify_kyc_invalid_status(self):
        result = verify_kyc(self.conn, "kyc-001", "invalid")
        self.assertEqual(result["error"], "Status must be 'approved' or 'rejected'")

    def test_verify_kyc_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = verify_kyc(self.conn, "kyc-999", "approved")
        self.assertEqual(result["error"], "KYC record kyc-999 not found")


class TestAssignRole(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_assign_role_returns_assignment_id(self):
        self.mock_cursor.fetchone.side_effect = [
            (["farm:read", "farm:write"],),  # default permissions
            ("assign-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),  # insert result
        ]
        result = assign_role(self.conn, "farmer-001", "farmer")
        self.assertIn("assignment_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["role"], "farmer")
        self.assertEqual(result["status"], "active")

    def test_assign_role_with_custom_permissions(self):
        self.mock_cursor.fetchone.return_value = (
            "assign-001", datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        result = assign_role(
            self.conn, "farmer-001", "admin",
            permissions=["farm:read", "farm:write", "farm:delete"],
        )
        self.assertEqual(len(result["permissions"]), 3)


class TestCheckPermission(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_check_permission_allowed(self):
        self.mock_cursor.fetchall.return_value = [
            ("farmer", "location", ["farm:read", "farm:write"]),
        ]
        result = check_permission(self.conn, "farmer-001", "farm", "read")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["role"], "farmer")

    def test_check_permission_denied(self):
        self.mock_cursor.fetchall.return_value = [
            ("farmer", "location", ["farm:read"]),
        ]
        result = check_permission(self.conn, "farmer-001", "farm", "delete")
        self.assertFalse(result["allowed"])

    def test_check_permission_wildcard(self):
        self.mock_cursor.fetchall.return_value = [
            ("admin", "global", ["*:read"]),
        ]
        result = check_permission(self.conn, "farmer-001", "farm", "read")
        self.assertTrue(result["allowed"])


class TestRecordDataSharingConsent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("consent-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_record_consent_returns_consent_id(self):
        result = record_data_sharing_consent(
            self.conn, "farmer-001", "soil_data", "buyer",
        )
        self.assertIn("consent_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["data_type"], "soil_data")
        self.assertEqual(result["recipient_type"], "buyer")
        self.assertTrue(result["consent_given"])

    def test_record_consent_calls_insert(self):
        record_data_sharing_consent(
            self.conn, "farmer-001", "yield_data", "researcher",
        )
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestRegisterDevice(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("reg-001", datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_register_device_returns_registration_id(self):
        result = register_device(
            self.conn, "farmer-001", "DEV001", "phone",
        )
        self.assertIn("registration_id", result)
        self.assertEqual(result["farmer_id"], "farmer-001")
        self.assertEqual(result["device_id"], "DEV001")
        self.assertEqual(result["device_type"], "phone")
        self.assertEqual(result["status"], "active")

    def test_register_device_calls_insert(self):
        register_device(self.conn, "farmer-001", "DEV002", "tablet")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()


class TestGetAccessMatrix(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_access_matrix_returns_entries(self):
        self.mock_cursor.description = [
            ("farmer_id",), ("farmer_name",), ("role",), ("scope",),
            ("permissions",), ("status",), ("assigned_at",), ("expires_at",),
            ("location_name",), ("kyc_status",), ("effective_status",),
        ]
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchall.return_value = [
            ("farmer-001", "John Doe", "farmer", "location", ["farm:read"], "active", now, None, "Adelphi", "verified", "active"),
        ]
        result = get_access_matrix(self.conn, location_id="loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["entries"][0]["role"], "farmer")

    def test_access_matrix_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("farmer_id",), ("farmer_name",), ("role",), ("scope",), ("permissions",), ("status",), ("assigned_at",), ("expires_at",), ("location_name",), ("kyc_status",), ("effective_status",)]
        result = get_access_matrix(self.conn, "loc-001")
        self.assertEqual(result["total"], 0)


class TestGetFarmerDirectory(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_directory_returns_farmers(self):
        self.mock_cursor.description = [
            ("farmer_id",), ("first_name",), ("last_name",), ("phone",),
            ("email",), ("village",), ("district",), ("province",), ("country",),
            ("farm_size_ha",), ("primary_crops",), ("farming_type",),
            ("kyc_status",), ("kyc_verified_at",), ("location_name",),
            ("primary_role",), ("role_scope",),
            ("active_credentials",), ("active_consents",), ("registered_devices",),
            ("status",), ("created_at",), ("updated_at",),
        ]
        now = datetime.now(timezone.utc)
        self.mock_cursor.fetchall.return_value = [
            ("farmer-001", "John", "Doe", "+1234567890", None,
             "Village A", "District B", "Province C", "Kenya",
             2.5, ["maize"], "conventional",
             "verified", now, "Adelphi",
             "farmer", "location",
             3, 2, 1,
             "active", now, now),
        ]
        result = get_farmer_directory(self.conn, location_id="loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["farmers"][0]["first_name"], "John")

    def test_directory_empty(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = [("farmer_id",), ("first_name",), ("last_name",), ("phone",), ("email",), ("village",), ("district",), ("province",), ("country",), ("farm_size_ha",), ("primary_crops",), ("farming_type",), ("kyc_status",), ("kyc_verified_at",), ("location_name",), ("primary_role",), ("role_scope",), ("active_credentials",), ("active_consents",), ("registered_devices",), ("status",), ("created_at",), ("updated_at",)]
        result = get_farmer_directory(self.conn, "loc-001")
        self.assertEqual(result["total"], 0)


if __name__ == "__main__":
    unittest.main()
