#!/usr/bin/env python3
"""
Tests for Data Governance & Interoperability
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone, timedelta

from services.analytics.data_governance import (
    record_consent,
    withdraw_consent,
    get_consent_status,
    check_consent,
    log_access,
    get_access_audit,
    request_portability,
    fulfill_portability,
    get_portability_requests,
    create_sharing_agreement,
    get_sharing_agreements,
    set_retention_policy,
    get_governance_summary,
)


class TestRecordConsent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "consent-001", datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_record_consent_creates_consent(self):
        result = record_consent(
            self.conn, "F001", "soil", "collection", status="granted",
        )
        self.assertIn("consent_id", result)
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["data_category"], "soil")
        self.assertEqual(result["consent_scope"], "collection")
        self.assertEqual(result["status"], "granted")

    def test_record_consent_completes(self):
        record_consent(self.conn, "F001", "soil", "collection")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()

    def test_record_consent_with_method(self):
        result = record_consent(
            self.conn, "F001", "soil", "collection", method="paper_form",
        )
        self.assertEqual(result["consent_method"], "paper_form")


class TestWithdrawConsent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "consent-001", "F001", "soil", "collection",
            datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_withdraw_consent_updates_status(self):
        result = withdraw_consent(
            self.conn, "consent-001", reason="No longer needed",
        )
        self.assertEqual(result["consent_id"], "consent-001")
        self.assertEqual(result["status"], "withdrawn")
        self.assertEqual(result["withdrawal_reason"], "No longer needed")

    def test_withdraw_consent_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = withdraw_consent(self.conn, "bad-id")
        self.assertIn("error", result)


class TestGetConsentStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("data_category",), ("consent_scope",), ("status",),
            ("granted_at",), ("withdrawn_at",), ("expires_at",),
            ("consent_method",), ("consent_version",), ("effective_status",),
            ("days_until_expiry",),
        ]

    def test_get_consent_status_returns_consents(self):
        self.mock_cursor.fetchall.return_value = [
            ("consent-001", "soil", "collection", "granted",
             datetime(2026, 1, 1, tzinfo=timezone.utc), None, None,
             "digital_form", "1.0", "granted", None),
        ]
        result = get_consent_status(self.conn, "F001")
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["total_active_consents"], 1)
        self.assertIn("soil", result["categories"])

    def test_get_consent_status_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_consent_status(self.conn, "F999")
        self.assertEqual(result["total_active_consents"], 0)


class TestCheckConsent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_check_consent_verifies_consent(self):
        # row[4] is consent_method; the code checks row[4] == "granted"
        self.mock_cursor.fetchone.return_value = (
            "consent-001", "granted", datetime(2026, 1, 1, tzinfo=timezone.utc),
            None, "granted", "granted",
        )
        result = check_consent(self.conn, "F001", "soil", "collection")
        self.assertTrue(result["consent_exists"])
        self.assertTrue(result["consented"])
        self.assertEqual(result["consent_id"], "consent-001")

    def test_check_consent_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = check_consent(self.conn, "F999", "soil", "collection")
        self.assertFalse(result["consent_exists"])
        self.assertFalse(result["consented"])


class TestLogAccess(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "log-001", datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_log_access_logs_event(self):
        result = log_access(
            self.conn, "A001", "soil", "soil_sample", "read",
            purpose="field review",
        )
        self.assertIn("access_log_id", result)
        self.assertEqual(result["accessor_id"], "A001")
        self.assertEqual(result["resource_type"], "soil_sample")
        self.assertEqual(result["access_type"], "read")
        self.assertEqual(result["status"], "success")

    def test_log_access_completes(self):
        log_access(self.conn, "A001", "soil", "soil_sample", "read")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetAccessAudit(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("accessor_id",), ("accessor_role",), ("accessor_type",),
            ("resource_type",), ("resource_id",), ("data_category",),
            ("access_type",), ("access_method",), ("purpose",),
            ("status",), ("denial_reason",), ("records_affected",),
            ("accessed_at",), ("location_name",),
        ]

    def test_get_access_audit_returns_audit_trail(self):
        self.mock_cursor.fetchall.return_value = [
            ("log-001", "A001", "admin", "user", "soil_sample",
             "res-001", "soil", "read", "api", "field review",
             "success", None, 1,
             datetime(2026, 7, 1, tzinfo=timezone.utc), "Adelphi"),
        ]
        result = get_access_audit(self.conn, "F001", days=30)
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["days"], 30)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["summary"]["total_events"], 1)

    def test_get_access_audit_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_access_audit(self.conn, "F999")
        self.assertEqual(result["summary"]["total_events"], 0)


class TestRequestPortability(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "req-001", datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_request_portability_creates_request(self):
        result = request_portability(
            self.conn, "F001", format_type="csv", scope="all",
        )
        self.assertIn("request_id", result)
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["scope"], "all")
        self.assertEqual(result["status"], "pending")

    def test_request_portability_completes(self):
        request_portability(self.conn, "F001")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestFulfillPortability(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "req-001", "F001", "csv", datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_fulfill_portability_updates_status(self):
        result = fulfill_portability(
            self.conn, "req-001", file_path="/tmp/export.csv",
            record_count=150,
        )
        self.assertEqual(result["request_id"], "req-001")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["output_url"], "/tmp/export.csv")
        self.assertEqual(result["record_count"], 150)

    def test_fulfill_portability_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = fulfill_portability(self.conn, "bad-id")
        self.assertIn("error", result)


class TestGetPortabilityRequests(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("data_categories",), ("format",), ("scope",),
            ("status",), ("requested_at",), ("processed_at",),
            ("ready_at",), ("downloaded_at",), ("expires_at",),
            ("output_url",), ("record_count",), ("output_size_bytes",),
            ("fair_principles",),
        ]

    def test_get_portability_requests_returns_requests(self):
        self.mock_cursor.fetchall.return_value = [
            ("req-001", ["soil"], "csv", "all", "ready",
             datetime(2026, 7, 1, tzinfo=timezone.utc),
             datetime(2026, 7, 1, tzinfo=timezone.utc),
             datetime(2026, 7, 1, tzinfo=timezone.utc),
             None, None, "/tmp/export.csv", 150, 1024, ["findable", "accessible"]),
        ]
        result = get_portability_requests(self.conn, "F001")
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["requests"][0]["status"], "ready")

    def test_get_portability_requests_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_portability_requests(self.conn, "F999")
        self.assertEqual(result["total"], 0)


class TestCreateSharingAgreement(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "agr-001", datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_create_sharing_agreement_creates_agreement(self):
        result = create_sharing_agreement(
            self.conn, "F001", "ORG001", ["soil", "yield"],
            purpose="research collaboration",
        )
        self.assertIn("agreement_id", result)
        self.assertEqual(result["provider_id"], "F001")
        self.assertEqual(result["consumer_id"], "ORG001")
        self.assertEqual(result["data_categories"], ["soil", "yield"])
        self.assertEqual(result["purpose"], "research collaboration")
        self.assertEqual(result["status"], "draft")

    def test_create_sharing_agreement_completes(self):
        create_sharing_agreement(
            self.conn, "F001", "ORG001", ["soil"], "research",
        )
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetSharingAgreements(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("provider_id",), ("consumer_id",), ("data_categories",),
            ("purpose",), ("status",), ("effective_date",), ("expiry_date",),
            ("anonymization_required",), ("commercial_use",), ("created_at",),
        ]

    def test_get_sharing_agreements_returns_agreements(self):
        self.mock_cursor.fetchall.return_value = [
            ("agr-001", "F001", "ORG001", ["soil"], "research",
             "active", date(2026, 1, 1), date(2027, 1, 1),
             True, False, datetime(2026, 7, 1, tzinfo=timezone.utc)),
        ]
        result = get_sharing_agreements(self.conn, "F001")
        self.assertEqual(result["farmer_id"], "F001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["agreements"][0]["status"], "active")

    def test_get_sharing_agreements_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_sharing_agreements(self.conn, "F999")
        self.assertEqual(result["total"], 0)


class TestSetRetentionPolicy(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = (
            "pol-001", datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def test_set_retention_policy_creates_policy(self):
        result = set_retention_policy(
            self.conn, "soil", 2555, action="soft_delete",
        )
        self.assertIn("policy_id", result)
        self.assertEqual(result["data_category"], "soil")
        self.assertEqual(result["retention_days"], 2555)
        self.assertEqual(result["deletion_method"], "soft_delete")
        self.assertEqual(result["status"], "active")

    def test_set_retention_policy_completes(self):
        set_retention_policy(self.conn, "soil", 2555)
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetGovernanceSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

        # get_governance_summary makes 1 fetchall + 5 fetchone calls
        # Use execute.side_effect to update description for the fetchall query
        self.descs = [
            [("data_category",), ("total_consents",), ("granted",),
             ("withdrawn",), ("expired",)],
            None,  # access summary (fetchone)
            None,  # agreements (fetchone)
            None,  # portability (fetchone)
            None,  # retention (fetchone)
        ]
        self.desc_idx = [0]
        def update_desc(*args, **kwargs):
            if self.desc_idx[0] < len(self.descs) and self.descs[self.desc_idx[0]] is not None:
                self.mock_cursor.description = self.descs[self.desc_idx[0]]
            self.desc_idx[0] += 1
        self.mock_cursor.execute.side_effect = update_desc

        self.mock_cursor.fetchall.side_effect = [
            [("soil", 5, 5, 0, 0)],
        ]
        self.mock_cursor.fetchone.side_effect = [
            (20, 1, 15, 3, 1, 1),
            (2,),
            (1,),
            (3, 2),
        ]

    def _make_summary(self):
        return get_governance_summary(self.conn, "loc-001")

    def test_get_governance_summary_aggregates_data(self):
        result = self._make_summary()
        self.assertEqual(result["location_id"], "loc-001")
        self.assertIn("consent", result)
        self.assertIn("access_audit", result)
        self.assertIn("sharing_agreements", result)
        self.assertIn("portability", result)
        self.assertIn("retention", result)

    def test_get_governance_summary_consent_metrics(self):
        result = self._make_summary()
        self.assertEqual(result["consent"]["total_granted"], 5)
        self.assertEqual(result["consent"]["total_withdrawn"], 0)
        self.assertEqual(result["consent"]["consent_rate_pct"], 100.0)

    def test_get_governance_summary_access_metrics(self):
        result = self._make_summary()
        self.assertEqual(result["access_audit"]["total_events_30d"], 20)
        self.assertEqual(result["access_audit"]["denied_30d"], 1)

    def test_get_governance_summary_closes_cursor(self):
        self._make_summary()
        self.mock_cursor.close.assert_called()


if __name__ == "__main__":
    unittest.main()
