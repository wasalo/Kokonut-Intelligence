#!/usr/bin/env python3
"""
Tests for Supply Chain Traceability
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone

from services.analytics.traceability import (
    create_produce_batch,
    record_custody_transfer,
    record_quality_inspection,
    verify_certification,
    log_provenance_event,
    get_batch_provenance,
    get_batch_status,
    list_batches,
    record_food_safety,
    get_certification_status,
    trace_forward,
    trace_backward,
    get_cold_chain_log,
)


class TestCreateProduceBatch(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("batch-001",)

    def test_create_produce_batch_returns_batch_id(self):
        result = create_produce_batch(
            self.conn, "loc-001", "maize", 500, harvest_date="2026-07-10",
        )
        self.assertIn("batch_id", result)
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["quantity"], 500)
        self.assertEqual(result["unit"], "kg")
        self.assertEqual(result["harvest_date"], "2026-07-10")
        self.assertEqual(result["status"], "active")

    def test_create_produce_batch_organic(self):
        result = create_produce_batch(
            self.conn, "loc-001", "maize", 500, organic=True,
        )
        self.assertTrue(result["organic"])

    def test_create_produce_batch_completes(self):
        create_produce_batch(self.conn, "loc-001", "maize", 500)
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()

    def test_create_produce_batch_logs_provenance(self):
        create_produce_batch(self.conn, "loc-001", "maize", 500)
        self.assertEqual(self.mock_cursor.execute.call_count, 2)


class TestRecordCustodyTransfer(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (500.0, "kg"),
            ("transfer-001",),
        ]

    def test_record_custody_transfer_creates_transfer(self):
        result = record_custody_transfer(
            self.conn, "batch-001", "Farm A", "Cooperative B",
            transfer_type="harvest_collection",
        )
        self.assertIn("transfer_id", result)
        self.assertEqual(result["from_actor"], "Farm A")
        self.assertEqual(result["to_actor"], "Cooperative B")
        self.assertEqual(result["transfer_type"], "harvest_collection")
        self.assertEqual(result["quantity"], 500.0)
        self.assertEqual(result["unit"], "kg")

    def test_record_custody_transfer_not_found(self):
        self.mock_cursor.fetchone.side_effect = None
        self.mock_cursor.fetchone.return_value = None
        with self.assertRaises(ValueError):
            record_custody_transfer(
                self.conn, "bad-id", "Farm A", "Cooperative B",
            )

    def test_record_custody_transfer_completes(self):
        record_custody_transfer(
            self.conn, "batch-001", "Farm A", "Cooperative B",
        )
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestRecordQualityInspection(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("insp-001",)

    def test_record_quality_inspection_records_inspection(self):
        result = record_quality_inspection(
            self.conn, "batch-001", "visual", "pass", grade="A",
            inspector="Inspector Jane",
        )
        self.assertIn("inspection_id", result)
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["inspection_type"], "visual")
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["inspector"], "Inspector Jane")

    def test_record_quality_inspection_completes(self):
        record_quality_inspection(self.conn, "batch-001", "visual", "pass")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestVerifyCertification(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("cert-001",)

    def test_verify_certification_records_verification(self):
        result = verify_certification(
            self.conn, "batch-001", "organic", "ORG-001", "KCB",
            expiry_date="2027-01-01",
        )
        self.assertIn("cert_id", result)
        self.assertEqual(result["cert_type"], "organic")
        self.assertEqual(result["cert_number"], "ORG-001")
        self.assertEqual(result["issuer"], "KCB")
        self.assertEqual(result["expiry_date"], "2027-01-01")
        self.assertTrue(result["verified"])

    def test_verify_certification_completes(self):
        verify_certification(
            self.conn, "batch-001", "organic", "ORG-001", "KCB",
        )
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestLogProvenanceEvent(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("event-001",)

    def test_log_provenance_event_logs_event(self):
        result = log_provenance_event(
            self.conn, "batch-001", "harvest", "Farmer John",
            location="Adelphi", description="Harvested 500kg maize",
        )
        self.assertIn("event_id", result)
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["event_type"], "harvest")
        self.assertEqual(result["actor"], "Farmer John")
        self.assertEqual(result["location"], "Adelphi")

    def test_log_provenance_event_completes(self):
        log_provenance_event(
            self.conn, "batch-001", "harvest", "Farmer John",
        )
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetBatchProvenance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_batch_provenance_returns_chain(self):
        self.mock_cursor.description = [
            ("id",), ("batch_id",), ("event_type",), ("actor",),
            ("location",), ("description",), ("evidence_url",),
            ("metadata",), ("created_at",),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [
                ("evt-001", "batch-001", "batch_created", "system:loc-001",
                 "loc-001", "Created batch", None, "{}", datetime(2026, 7, 10, tzinfo=timezone.utc)),
                ("evt-002", "batch-001", "custody_harvest", "Farmer",
                 "Adelphi", "Transfer", None, "{}", datetime(2026, 7, 11, tzinfo=timezone.utc)),
            ],
            ("batch-001", "maize", None, 500, "kg", "2026-07-10", False, "active"),
        ]
        result = get_batch_provenance(self.conn, "batch-001")
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["event_count"], 2)
        self.assertIsNotNone(result["batch"])

    def test_get_batch_provenance_empty(self):
        self.mock_cursor.fetchall.side_effect = [[], None]
        result = get_batch_provenance(self.conn, "batch-001")
        self.assertEqual(result["event_count"], 0)


class TestGetBatchStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_batch_status_returns_status(self):
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("crop_name",), ("variety",),
            ("quantity",), ("unit",), ("harvest_date",), ("organic",),
            ("status",), ("created_at",),
        ]
        self.mock_cursor.fetchone.side_effect = [
            ("batch-001", "loc-001", "maize", "H614", 500, "kg",
             date(2026, 7, 10), False, "active", datetime(2026, 7, 10, tzinfo=timezone.utc)),
            ("Cooperative B", "sale", 500.0, "Nairobi", datetime(2026, 7, 11, tzinfo=timezone.utc)),
            (5,),
        ]
        result = get_batch_status(self.conn, "batch-001")
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["current_holder"], "Cooperative B")
        self.assertEqual(result["event_count"], 5)

    def test_get_batch_status_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_batch_status(self.conn, "bad-id")
        self.assertIn("error", result)


class TestListBatches(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_batches_filters_correctly(self):
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("crop_name",), ("variety",),
            ("quantity",), ("unit",), ("harvest_date",), ("organic",),
            ("status",), ("created_at",),
        ]
        self.mock_cursor.fetchall.return_value = [
            ("batch-001", "loc-001", "maize", None, 500, "kg",
             date(2026, 7, 10), False, "active", datetime(2026, 7, 10, tzinfo=timezone.utc)),
        ]
        result = list_batches(self.conn, location_id="loc-001", status="active")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["batches"][0]["crop_name"], "maize")

    def test_list_batches_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = list_batches(self.conn, location_id="loc-999")
        self.assertEqual(result["count"], 0)


class TestRecordFoodSafety(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("check-001",)

    def test_record_food_safety_records_check(self):
        result = record_food_safety(
            self.conn, "batch-001", "temperature", "pass",
            temperature=4.2, inspector="Safety Officer",
        )
        self.assertIn("check_id", result)
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["check_type"], "temperature")
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["temperature"], 4.2)

    def test_record_food_safety_completes(self):
        record_food_safety(self.conn, "batch-001", "temperature", "pass")
        self.conn.commit.assert_called_once()
        self.mock_cursor.close.assert_called_once()


class TestGetCertificationStatus(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_get_certification_status_returns_certs(self):
        self.mock_cursor.fetchall.return_value = [
            ("cert-001", "batch-001", "organic", "ORG-001", "KCB",
             date(2027, 1, 1), True, "maize", 500, "kg"),
        ]
        result = get_certification_status(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["active"]), 1)
        self.assertEqual(len(result["expired"]), 0)

    def test_get_certification_status_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_certification_status(self.conn, "loc-999")
        self.assertEqual(result["total"], 0)
        self.assertEqual(len(result["active"]), 0)


class TestTraceForward(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_trace_forward_returns_downstream(self):
        self.mock_cursor.fetchone.side_effect = [
            ("batch-001", "maize", 500, "kg", "active"),
        ]
        self.mock_cursor.fetchall.side_effect = [
            [
                ("Cooperative B", "sale", 500.0, "Nairobi",
                 datetime(2026, 7, 11, tzinfo=timezone.utc), "Sold"),
            ],
            [],
        ]
        result = trace_forward(self.conn, "batch-001")
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["transfer_count"], 1)
        self.assertEqual(len(result["downstream_chain"]), 1)

    def test_trace_forward_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = trace_forward(self.conn, "bad-id")
        self.assertIn("error", result)


class TestTraceBackward(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_trace_backward_returns_origin(self):
        self.mock_cursor.fetchone.side_effect = [
            ("batch-001", "loc-001", "maize", 500, "kg",
             date(2026, 7, 10), False, "active"),
        ]
        # Update description for batch, custody_transfer, and provenance_event queries
        batch_desc = [
            ("id",), ("location_id",), ("crop_name",), ("variety",),
            ("quantity",), ("unit",), ("harvest_date",), ("organic",),
            ("status",),
        ]
        custody_desc = [
            ("from_actor",), ("transfer_type",), ("quantity",),
            ("location",), ("created_at",), ("notes",),
        ]
        provenance_desc = [
            ("event_type",), ("actor",), ("location",), ("description",),
            ("evidence_url",), ("created_at",),
        ]
        desc_list = [batch_desc, custody_desc, provenance_desc]
        desc_idx = [0]
        def update_desc(*args, **kwargs):
            if desc_idx[0] < len(desc_list) and desc_list[desc_idx[0]] is not None:
                self.mock_cursor.description = desc_list[desc_idx[0]]
            desc_idx[0] += 1
        self.mock_cursor.execute.side_effect = update_desc

        self.mock_cursor.fetchall.side_effect = [
            [
                ("Farmer John", "harvest", 500.0, "Adelphi",
                 datetime(2026, 7, 10, tzinfo=timezone.utc), "Harvested"),
            ],
            [
                ("harvest", "Farmer John", "Adelphi", "Harvested",
                 None, datetime(2026, 7, 10, tzinfo=timezone.utc)),
            ],
        ]
        result = trace_backward(self.conn, "batch-001")
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["crop_name"], "maize")
        self.assertEqual(result["origin_location_id"], "loc-001")
        self.assertEqual(result["first_handler"], "Farmer John")
        self.assertEqual(len(result["upstream_chain"]), 1)
        self.assertEqual(len(result["provenance_events"]), 1)

    def test_trace_backward_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = trace_backward(self.conn, "bad-id")
        self.assertIn("error", result)


class TestGetColdChainLog(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.description = [
            ("id",), ("check_type",), ("result",), ("temperature",),
            ("inspector",), ("notes",), ("metadata",), ("created_at",),
        ]

    def test_get_cold_chain_log_returns_temperature_log(self):
        self.mock_cursor.fetchall.return_value = [
            ("chk-001", "temperature", "pass", 4.0, "Inspector",
             None, "{}", datetime(2026, 7, 10, tzinfo=timezone.utc)),
            ("chk-002", "temperature", "pass", 4.5, "Inspector",
             None, "{}", datetime(2026, 7, 11, tzinfo=timezone.utc)),
            ("chk-003", "cold_chain", "pass", 3.8, "Inspector",
             None, "{}", datetime(2026, 7, 12, tzinfo=timezone.utc)),
        ]
        result = get_cold_chain_log(self.conn, "batch-001")
        self.assertEqual(result["batch_id"], "batch-001")
        self.assertEqual(result["total_checks"], 3)
        self.assertIn("temperature_stats", result)
        self.assertEqual(result["temperature_stats"]["min_temp"], 3.8)
        self.assertEqual(result["temperature_stats"]["max_temp"], 4.5)
        self.assertEqual(result["temperature_stats"]["readings"], 3)

    def test_get_cold_chain_log_empty(self):
        self.mock_cursor.fetchall.return_value = []
        result = get_cold_chain_log(self.conn, "batch-001")
        self.assertEqual(result["total_checks"], 0)
        self.assertEqual(result["temperature_stats"], {})


class TestCanonicalSchemaContract(unittest.TestCase):

    def test_write_queries_use_canonical_traceability_tables(self):
        cases = [
            (create_produce_batch, ("loc-001", "maize", 500), "produce_batch"),
            (record_quality_inspection, ("batch-001", "visual", "pass"), "quality_inspection"),
            (log_provenance_event, ("batch-001", "harvest", "Farmer"), "provenance_event"),
            (record_food_safety, ("batch-001", "temperature", "pass"), "food_safety_record"),
        ]
        for function, args, expected_table in cases:
            with self.subTest(function=function.__name__):
                conn = MagicMock()
                function(conn, *args)
                sql = " ".join(str(call.args[0]) for call in conn.cursor.return_value.execute.call_args_list)
                self.assertIn(f"INSERT INTO {expected_table}", sql)
                self.assertNotIn("INSERT INTO custody_transfer", sql)
                self.assertNotIn("INSERT INTO certification_record", sql)
                self.assertNotIn("INSERT INTO food_safety_check", sql)

    def test_custody_query_uses_canonical_table_and_sequence(self):
        conn = MagicMock()
        conn.cursor.return_value.fetchone.side_effect = [(500, "kg"), (1,)]
        record_custody_transfer(conn, "batch-001", "Farm", "Coop")
        sql = " ".join(str(call.args[0]) for call in conn.cursor.return_value.execute.call_args_list)
        self.assertIn("INSERT INTO chain_of_custody", sql)
        self.assertIn("sequence_num", sql)
        self.assertIn("from_actor_type", sql)
        self.assertIn("to_actor_type", sql)

    def test_certification_query_uses_canonical_tables(self):
        conn = MagicMock()
        conn.cursor.return_value.fetchone.side_effect = [("loc-001",), ("type-001",)]
        verify_certification(conn, "batch-001", "organic", "ORG-001", "KCB")
        sql = " ".join(str(call.args[0]) for call in conn.cursor.return_value.execute.call_args_list)
        self.assertIn("FROM certification_type", sql)
        self.assertIn("INSERT INTO certification_verify", sql)
        self.assertIn("location_id", sql)
        self.assertIn("issued_date", sql)

    def test_write_rolls_back_when_second_statement_fails(self):
        conn = MagicMock()
        conn.cursor.return_value.execute.side_effect = [None, RuntimeError("provenance failed")]
        with self.assertRaises(RuntimeError):
            create_produce_batch(conn, "loc-001", "maize", 500)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
