#!/usr/bin/env python3
"""
Tests for Integrated Pest Management
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, PropertyMock
from datetime import date, timedelta

from services.analytics.pest_management import (
    record_scouting,
    set_action_threshold,
    check_threshold,
    record_intervention,
    record_pesticide_application,
    record_resistance,
    record_degree_day,
    get_pest_summary,
    get_pesticide_usage,
    get_degree_day_tracking,
    recommend_intervention,
    get_pest_dashboard,
    add_pest_reference,
    get_pest_reference,
    list_pest_references,
    create_scouting_schedule,
    get_due_scouting,
    record_scouting_completion,
    get_scouting_compliance,
    schedule_re_scout,
    evaluate_intervention,
    compute_ipm_compliance_score,
    add_pest_crop_interaction,
    get_pest_crop_interactions,
    recommend_management_for_crop,
    add_trap,
    record_trap_catch,
    get_trap_trends,
    check_trap_threshold,
    add_mode_of_action,
    check_rotation,
    get_rotation_history,
    get_optimal_spray_windows,
    compute_organic_pest_score,
    generate_ipm_audit,
)


class TestRecordScouting(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_scouting_id(self):
        result = record_scouting(self.conn, "loc-001", "fall_armyworm")
        self.assertIn("scouting_id", result)
        self.assertIsNotNone(result["scouting_id"])

    def test_records_pest_name(self):
        result = record_scouting(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(result["pest_name"], "fall_armyworm")

    def test_records_severity(self):
        result = record_scouting(
            self.conn, "loc-001", "fall_armyworm", severity="moderate",
        )
        self.assertEqual(result["severity"], "moderate")

    def test_records_incidence(self):
        result = record_scouting(
            self.conn, "loc-001", "fall_armyworm", incidence_pct=15.5,
        )
        self.assertEqual(result["incidence_pct"], 15.5)

    def test_records_custom_date(self):
        d = date(2026, 3, 15)
        result = record_scouting(
            self.conn, "loc-001", "fall_armyworm", scout_date=d,
        )
        self.assertEqual(result["scout_date"], "2026-03-15")

    def test_executes_insert(self):
        record_scouting(self.conn, "loc-001", "fall_armyworm")
        self.mock_cursor.execute.assert_called_once()
        self.conn.commit.assert_called_once()

    def test_records_location_id(self):
        result = record_scouting(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(result["location_id"], "loc-001")


class TestSetActionThreshold(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_threshold_id(self):
        result = set_action_threshold(
            self.conn, "loc-001", "fall_armyworm", crop_name="maize",
        )
        self.assertIn("threshold_id", result)
        self.assertIsNotNone(result["threshold_id"])

    def test_records_eil(self):
        result = set_action_threshold(
            self.conn, "loc-001", "fall_armyworm",
            economic_injury_level=2.0,
        )
        self.assertEqual(result["economic_injury_level"], 2.0)

    def test_records_et(self):
        result = set_action_threshold(
            self.conn, "loc-001", "fall_armyworm",
            economic_threshold=1.0,
        )
        self.assertEqual(result["economic_threshold"], 1.0)

    def test_records_crop_name(self):
        result = set_action_threshold(
            self.conn, "loc-001", "fall_armyworm", crop_name="maize",
        )
        self.assertEqual(result["crop_name"], "maize")

    def test_commits(self):
        set_action_threshold(self.conn, "loc-001", "fall_armyworm")
        self.conn.commit.assert_called_once()


class TestCheckThreshold(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_no_threshold_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = check_threshold(
            self.conn, "loc-001", "fall_armyworm", current_count=3.0,
        )
        self.assertFalse(result["threshold_found"])
        self.assertEqual(result["action_recommended"], "monitor")

    def test_below_threshold(self):
        self.mock_cursor.fetchone.return_value = (
            "thr-001", 5.0, 3.0, "per_plant", None,
        )
        result = check_threshold(
            self.conn, "loc-001", "fall_armyworm", current_count=1.0,
        )
        self.assertFalse(result["above_threshold"])
        self.assertEqual(result["action_recommended"], "continue_monitoring")

    def test_above_et(self):
        self.mock_cursor.fetchone.return_value = (
            "thr-001", 5.0, 3.0, "per_plant", None,
        )
        result = check_threshold(
            self.conn, "loc-001", "fall_armyworm", current_count=4.0,
        )
        self.assertTrue(result["above_threshold"])
        self.assertEqual(result["action_recommended"], "intervention_recommended")

    def test_above_eil(self):
        self.mock_cursor.fetchone.return_value = (
            "thr-001", 5.0, 3.0, "per_plant", None,
        )
        result = check_threshold(
            self.conn, "loc-001", "fall_armyworm", current_count=6.0,
        )
        self.assertTrue(result["above_eil"])
        self.assertEqual(result["action_recommended"], "immediate_intervention")

    def test_returns_threshold_id(self):
        self.mock_cursor.fetchone.return_value = (
            "thr-001", 5.0, 3.0, "per_plant", None,
        )
        result = check_threshold(
            self.conn, "loc-001", "fall_armyworm", current_count=1.0,
        )
        self.assertEqual(result["threshold_id"], "thr-001")


class TestRecordIntervention(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_intervention_id(self):
        result = record_intervention(
            self.conn, "loc-001", "biological",
        )
        self.assertIn("intervention_id", result)
        self.assertIsNotNone(result["intervention_id"])

    def test_records_type(self):
        result = record_intervention(
            self.conn, "loc-001", "biological",
        )
        self.assertEqual(result["intervention_type"], "biological")

    def test_records_method(self):
        result = record_intervention(
            self.conn, "loc-001", "biological", method_name="Bt spray",
        )
        self.assertEqual(result["method_name"], "Bt spray")

    def test_records_date(self):
        d = date(2026, 4, 1)
        result = record_intervention(
            self.conn, "loc-001", "chemical", intervention_date=d,
        )
        self.assertEqual(result["intervention_date"], "2026-04-01")

    def test_commits(self):
        record_intervention(self.conn, "loc-001", "cultural")
        self.conn.commit.assert_called_once()


class TestRecordPesticideApplication(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_application_id(self):
        result = record_pesticide_application(
            self.conn, "loc-001", "Bt spray",
        )
        self.assertIn("application_id", result)

    def test_records_product_name(self):
        result = record_pesticide_application(
            self.conn, "loc-001", "Bt spray",
        )
        self.assertEqual(result["product_name"], "Bt spray")

    def test_records_active_ingredient(self):
        result = record_pesticide_application(
            self.conn, "loc-001", "Bt spray",
            active_ingredient="Bacillus thuringiensis",
        )
        self.assertEqual(result["active_ingredient"], "Bacillus thuringiensis")

    def test_records_chemical_class(self):
        result = record_pesticide_application(
            self.conn, "loc-001", "Bt spray",
            chemical_class="bioinsecticide",
        )
        self.assertEqual(result["chemical_class"], "bioinsecticide")

    def test_records_area(self):
        result = record_pesticide_application(
            self.conn, "loc-001", "Bt spray", area_ha=1.5,
        )
        self.assertEqual(result["area_ha"], 1.5)

    def test_commits(self):
        record_pesticide_application(self.conn, "loc-001", "Bt spray")
        self.conn.commit.assert_called_once()


class TestRecordResistance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_resistance_id(self):
        result = record_resistance(
            self.conn, "loc-001", "fall_armyworm", "pyrethroid", "moderate",
        )
        self.assertIn("resistance_id", result)

    def test_records_pest_name(self):
        result = record_resistance(
            self.conn, "loc-001", "fall_armyworm", "pyrethroid", "moderate",
        )
        self.assertEqual(result["pest_name"], "fall_armyworm")

    def test_records_level(self):
        result = record_resistance(
            self.conn, "loc-001", "fall_armyworm", "pyrethroid", "high",
        )
        self.assertEqual(result["resistance_level"], "high")

    def test_records_date(self):
        d = date(2026, 5, 10)
        result = record_resistance(
            self.conn, "loc-001", "fall_armyworm", "pyrethroid",
            "moderate", observation_date=d,
        )
        self.assertEqual(result["observation_date"], "2026-05-10")

    def test_commits(self):
        record_resistance(
            self.conn, "loc-001", "fall_armyworm", "pyrethroid", "low",
        )
        self.conn.commit.assert_called_once()


class TestRecordDegreeDay(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.side_effect = [
            (0.0,),   # previous cumulative
            None,      # no degree day config
        ]

    def test_returns_degree_day_id(self):
        result = record_degree_day(
            self.conn, "loc-001", "fall_armyworm",
            max_temp=30.0, min_temp=20.0,
        )
        self.assertIn("degree_day_id", result)

    def test_computes_degree_days(self):
        result = record_degree_day(
            self.conn, "loc-001", "fall_armyworm",
            base_temp=10.0, max_temp=30.0, min_temp=20.0,
        )
        self.assertEqual(result["degree_days"], 15.0)

    def test_records_location(self):
        result = record_degree_day(
            self.conn, "loc-001", "fall_armyworm",
            max_temp=30.0, min_temp=20.0,
        )
        self.assertEqual(result["location_id"], "loc-001")

    def test_cumulative(self):
        self.mock_cursor.fetchone.side_effect = [
            (25.0,),  # previous cumulative
            None,     # no config
        ]
        result = record_degree_day(
            self.conn, "loc-001", "fall_armyworm",
            base_temp=10.0, max_temp=30.0, min_temp=20.0,
        )
        self.assertEqual(result["cumulative_degree_days"], 40.0)


class TestGetPestSummary(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("pest_name",), ("pest_type",), ("severity",), ("observations",),
             ("avg_incidence",), ("avg_damage",), ("last_scouted",)],
            [("intervention_type",), ("count",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], []]
        self.mock_cursor.fetchone.side_effect = [(0,), (0,)]
        result = get_pest_summary(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_pests_list(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [("fall_armyworm", "insect", "moderate", 5, 15.0, 5.0, "2026-01-01")],
            [("biological", 3)],
        ]
        self.mock_cursor.fetchone.side_effect = [(2,), (0,)]
        result = get_pest_summary(self.conn, "loc-001")
        self.assertIsInstance(result["pests"], list)
        self.assertEqual(len(result["pests"]), 1)

    def test_returns_intervention_counts(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [
            [],
            [("biological", 5), ("chemical", 2)],
        ]
        self.mock_cursor.fetchone.side_effect = [(0,), (0,)]
        result = get_pest_summary(self.conn, "loc-001")
        self.assertEqual(result["intervention_counts"]["biological"], 5)


class TestGetPesticideUsage(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_usage(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("chemical_class",), ("product_name",), ("application_count",),
            ("total_volume",), ("volume_unit",), ("total_area_treated",),
            ("avg_rei_days",), ("avg_phi_days",),
        ])
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = (0, 0)
        result = get_pesticide_usage(self.conn, "loc-001", days=30)
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["period_days"], 30)

    def test_returns_totals(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("chemical_class",), ("product_name",), ("application_count",),
            ("total_volume",), ("volume_unit",), ("total_area_treated",),
            ("avg_rei_days",), ("avg_phi_days",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("insecticide", "Bt", 3, 15.0, "L", 5.0, 7, 14),
        ]
        self.mock_cursor.fetchone.return_value = (3, 15.0)
        result = get_pesticide_usage(self.conn, "loc-001", days=30)
        self.assertEqual(result["total_applications"], 3)
        self.assertEqual(result["total_volume_used"], 15.0)


class TestGetDegreeDayTracking(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_tracking(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("record_date",), ("base_temp",), ("upper_temp",),
            ("max_temp",), ("min_temp",), ("degree_days",),
            ("cumulative_degree_days",), ("lifecycle_stage",), ("source",),
        ])
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.side_effect = [None, None]
        result = get_degree_day_tracking(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(result["location_id"], "loc-001")
        self.assertEqual(result["pest_name"], "fall_armyworm")

    def test_returns_records(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("record_date",), ("base_temp",), ("upper_temp",),
            ("max_temp",), ("min_temp",), ("degree_days",),
            ("cumulative_degree_days",), ("lifecycle_stage",), ("source",),
        ])
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 1, 1), 10.0, 38.0, 30.0, 20.0, 15.0, 15.0, "larva", "sensor"),
        ]
        self.mock_cursor.fetchone.side_effect = [
            (300.0, [{"name": "egg", "dd_start": 0, "dd_end": 50}]),
            (3.0, 5.0),
        ]
        result = get_degree_day_tracking(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(len(result["recent_records"]), 1)
        self.assertEqual(result["total_degree_days_for_lifecycle"], 300.0)


class TestRecommendIntervention(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_error_for_missing_record(self):
        self.mock_cursor.fetchone.return_value = None
        result = recommend_intervention(self.conn, "nonexistent")
        self.assertIn("error", result)

    def test_low_severity_cultural(self):
        self.mock_cursor.fetchone.return_value = (
            "scout-001", "loc-001", "fall_armyworm", "insect",
            "low", 5.0, 2.0, None,
        )
        result = recommend_intervention(self.conn, "scout-001")
        self.assertEqual(result["severity"], "low")
        self.assertGreater(len(result["recommendations"]), 0)
        types = [r["type"] for r in result["recommendations"]]
        self.assertIn("cultural", types)

    def test_high_severity_chemical(self):
        self.mock_cursor.fetchone.return_value = (
            "scout-001", "loc-001", "fall_armyworm", "insect",
            "high", 40.0, 25.0, None,
        )
        result = recommend_intervention(self.conn, "scout-001")
        types = [r["type"] for r in result["recommendations"]]
        self.assertIn("chemical", types)

    def test_moderate_severity(self):
        self.mock_cursor.fetchone.return_value = (
            "scout-001", "loc-001", "fall_armyworm", "insect",
            "moderate", 20.0, 10.0, None,
        )
        result = recommend_intervention(self.conn, "scout-001")
        self.assertGreaterEqual(len(result["recommendations"]), 2)


class TestGetPestDashboard(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def _mock_descriptions(self):
        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("pest_name",), ("pest_type",), ("severity",), ("count",),
             ("avg_incidence",), ("avg_damage",), ("last_scouted",)],
            [("intervention_type",), ("count",), ("avg_effectiveness",)],
            [("chemical_class",), ("applications",), ("total_volume",), ("volume_unit",)],
            [("pest_name",), ("chemical_class",), ("resistance_level",)],
            [("pest_name",), ("current_cdd",), ("current_stage",), ("last_recorded",)],
        ])

    def test_returns_location_id(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], [], []]
        self.mock_cursor.fetchone.side_effect = [(0,), (0,)]
        result = get_pest_dashboard(self.conn, "loc-001")
        self.assertEqual(result["location_id"], "loc-001")

    def test_returns_all_sections(self):
        self._mock_descriptions()
        self.mock_cursor.fetchall.side_effect = [[], [], [], [], []]
        self.mock_cursor.fetchone.side_effect = [(5,), (3,)]
        result = get_pest_dashboard(self.conn, "loc-001")
        self.assertIn("pest_activity", result)
        self.assertIn("interventions", result)
        self.assertIn("chemical_use", result)
        self.assertIn("resistance_alerts", result)
        self.assertIn("degree_days", result)
        self.assertEqual(result["high_severity_count"], 5)
        self.assertEqual(result["total_interventions"], 3)


# ============================================================
# Phase 13A: Pest Biology Reference Tests
# ============================================================

class TestAddPestReference(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_reference_id(self):
        result = add_pest_reference(self.conn, "fall_armyworm")
        self.assertIn("reference_id", result)
        self.assertIsNotNone(result["reference_id"])

    def test_records_pest_name(self):
        result = add_pest_reference(self.conn, "fall_armyworm")
        self.assertEqual(result["pest_name"], "fall_armyworm")

    def test_records_scientific_name(self):
        result = add_pest_reference(
            self.conn, "fall_armyworm", scientific_name="Spodoptera frugiperda",
        )
        self.assertEqual(result["scientific_name"], "Spodoptera frugiperda")

    def test_records_common_name(self):
        result = add_pest_reference(
            self.conn, "fall_armyworm", common_name="Fall Armyworm",
        )
        self.assertEqual(result["common_name"], "Fall Armyworm")

    def test_commits(self):
        add_pest_reference(self.conn, "fall_armyworm")
        self.conn.commit.assert_called_once()

    def test_on_conflict_updates(self):
        add_pest_reference(self.conn, "fall_armyworm", common_name="FAW")
        add_pest_reference(self.conn, "fall_armyworm", common_name="Fall Armyworm")
        self.assertEqual(self.mock_cursor.execute.call_count, 2)


class TestGetPestReference(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_reference(self):
        self.mock_cursor.fetchone.return_value = (
            "ref-001", "fall_armyworm", "Spodoptera frugiperda", "Fall Armyworm",
            "insect", 10.0, 38.0, 550.0,
            [{"name": "egg", "dd_start": 0, "dd_end": 30}],
            ["maize", "sorghum"],
            [{"name": "Trichogramma", "type": "parasitoid"}],
            "Larvae feed on leaves", "critical", "Africa",
        )
        result = get_pest_reference(self.conn, "fall_armyworm")
        self.assertEqual(result["pest_name"], "fall_armyworm")
        self.assertEqual(result["scientific_name"], "Spodoptera frugiperda")
        self.assertEqual(result["base_temp"], 10.0)
        self.assertEqual(result["host_crops"], ["maize", "sorghum"])

    def test_returns_error_for_missing(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_pest_reference(self.conn, "nonexistent")
        self.assertIn("error", result)


class TestListPestReferences(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_list(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("pest_name",), ("scientific_name",), ("common_name",),
            ("pest_category",), ("economic_importance",), ("host_crops",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("fall_armyworm", "Spodoptera", "FAW", "insect", "critical", ["maize"]),
        ]
        result = list_pest_references(self.conn)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["references"][0]["pest_name"], "fall_armyworm")

    def test_filters_by_category(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("pest_name",), ("scientific_name",), ("common_name",),
            ("pest_category",), ("economic_importance",), ("host_crops",),
        ])
        self.mock_cursor.fetchall.return_value = []
        result = list_pest_references(self.conn, pest_category="fungal")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["pest_category"], "fungal")


# ============================================================
# Phase 13A: Scouting Schedule Tests
# ============================================================

class TestCreateScoutingSchedule(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_schedule_id(self):
        result = create_scouting_schedule(
            self.conn, "loc-001", "fall_armyworm",
        )
        self.assertIn("schedule_id", result)
        self.assertIsNotNone(result["schedule_id"])

    def test_records_frequency(self):
        result = create_scouting_schedule(
            self.conn, "loc-001", "fall_armyworm", frequency_days=14,
        )
        self.assertEqual(result["frequency_days"], 14)

    def test_records_pest_name(self):
        result = create_scouting_schedule(
            self.conn, "loc-001", "fall_armyworm",
        )
        self.assertEqual(result["pest_name"], "fall_armyworm")

    def test_commits(self):
        create_scouting_schedule(self.conn, "loc-001", "fall_armyworm")
        self.conn.commit.assert_called_once()


class TestGetDueScouting(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_schedules(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("id",), ("pest_name",), ("crop_name",), ("frequency_days",),
            ("assigned_to",), ("start_date",), ("end_date",), ("last_scouted",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("sch-001", "fall_armyworm", "maize", 7, None, date(2026, 1, 1), None, date(2026, 7, 1)),
        ]
        result = get_due_scouting(self.conn, "loc-001")
        self.assertEqual(result["total_schedules"], 1)
        self.assertIn("schedules", result)

    def test_empty_schedules(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("id",), ("pest_name",), ("crop_name",), ("frequency_days",),
            ("assigned_to",), ("start_date",), ("end_date",), ("last_scouted",),
        ])
        self.mock_cursor.fetchall.return_value = []
        result = get_due_scouting(self.conn, "loc-001")
        self.assertEqual(result["total_schedules"], 0)
        self.assertEqual(result["overdue_count"], 0)


class TestRecordScoutingCompletion(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_compliance_id(self):
        self.mock_cursor.fetchone.side_effect = [
            ("sch-001", 7),  # schedule row
            (date(2026, 7, 1),),  # last date
        ]
        result = record_scouting_completion(
            self.conn, "sch-001", "scout-001",
        )
        self.assertIn("compliance_id", result)
        self.assertIsNotNone(result["compliance_id"])

    def test_records_on_time(self):
        self.mock_cursor.fetchone.side_effect = [
            ("sch-001", 7),
            (date(2026, 7, 1),),
        ]
        result = record_scouting_completion(
            self.conn, "sch-001", "scout-001", scout_date=date(2026, 7, 5),
        )
        self.assertEqual(result["status"], "on_time")

    def test_returns_error_for_missing_schedule(self):
        self.mock_cursor.fetchone.return_value = None
        result = record_scouting_completion(self.conn, "bad-id", "scout-001")
        self.assertIn("error", result)


class TestGetScoutingCompliance(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_compliance(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("pest_name",), ("crop_name",), ("frequency_days",),
            ("total_scheduled",), ("on_time",), ("late",),
            ("missed",), ("skipped",), ("compliance_pct",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("fall_armyworm", "maize", 7, 4, 3, 1, 0, 0, 75.0),
        ]
        result = get_scouting_compliance(self.conn, "loc-001")
        self.assertIn("overall_compliance_pct", result)
        self.assertEqual(len(result["by_pest"]), 1)


# ============================================================
# Phase 13A: Re-scout & Evaluation Tests
# ============================================================

class TestScheduleReScout(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_re_scout_date(self):
        self.mock_cursor.fetchone.return_value = ("int-001",)
        result = schedule_re_scout(self.conn, "int-001", date(2026, 7, 15))
        self.assertEqual(result["re_scout_date"], "2026-07-15")

    def test_returns_error_for_missing(self):
        self.mock_cursor.fetchone.return_value = None
        result = schedule_re_scout(self.conn, "bad-id", date(2026, 7, 15))
        self.assertIn("error", result)


class TestEvaluateIntervention(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_evaluation(self):
        self.mock_cursor.fetchone.return_value = (
            "int-001", "biological", "fall_armyworm", None,
        )
        result = evaluate_intervention(self.conn, "int-001", "scout-002", 75.0)
        self.assertEqual(result["actual_effectiveness_pct"], 75.0)
        self.assertTrue(result["effective"])

    def test_marks_ineffective_below_50(self):
        self.mock_cursor.fetchone.return_value = (
            "int-001", "chemical", "fall_armyworm", None,
        )
        result = evaluate_intervention(self.conn, "int-001", "scout-002", 30.0)
        self.assertFalse(result["effective"])

    def test_returns_error_for_missing(self):
        self.mock_cursor.fetchone.return_value = None
        result = evaluate_intervention(self.conn, "bad-id", "scout-001", 50.0)
        self.assertIn("error", result)


# ============================================================
# Phase 13A: IPM Compliance Score Tests
# ============================================================

class TestComputeIpmComplianceScore(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_score_components(self):
        self.mock_cursor.fetchone.side_effect = [
            (10,),   # total_scouts
            (1,),    # total_schedules
            (3,),    # on_time compliance
            (0,),    # premature_chem
            (5,),    # total_interventions
            (2,),    # types query
            (8,),    # with_evidence
        ]
        self.mock_cursor.fetchall.return_value = [
            ("biological",), ("chemical",),
        ]
        result = compute_ipm_compliance_score(self.conn, "loc-001")
        self.assertIn("overall_compliance_score", result)
        self.assertIn("scouting_score", result)
        self.assertIn("threshold_adherence_score", result)
        self.assertIn("ladder_compliance_score", result)
        self.assertIn("record_completeness_score", result)

    def test_score_range(self):
        self.mock_cursor.fetchone.side_effect = [
            (5,), (0,), (0,), (0,), (3,), (1,), (4,),
        ]
        self.mock_cursor.fetchall.return_value = [("biological",)]
        result = compute_ipm_compliance_score(self.conn, "loc-001")
        score = result["overall_compliance_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_no_interventions(self):
        self.mock_cursor.fetchone.side_effect = [
            (5,), (0,), (0,), (0,), (0,), (0,), (3,),
        ]
        self.mock_cursor.fetchall.return_value = []
        result = compute_ipm_compliance_score(self.conn, "loc-001")
        self.assertIn("overall_compliance_score", result)


# ============================================================
# Phase 13B: Pest-Crop Interaction Tests
# ============================================================

class TestAddPestCropInteraction(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_interaction_id(self):
        result = add_pest_crop_interaction(
            self.conn, "fall_armyworm", "maize",
        )
        self.assertIn("interaction_id", result)
        self.assertIsNotNone(result["interaction_id"])

    def test_records_pest_and_crop(self):
        result = add_pest_crop_interaction(
            self.conn, "fall_armyworm", "maize",
        )
        self.assertEqual(result["pest_name"], "fall_armyworm")
        self.assertEqual(result["crop_name"], "maize")

    def test_records_yield_loss(self):
        result = add_pest_crop_interaction(
            self.conn, "fall_armyworm", "maize", yield_loss_potential=50.0,
        )
        self.assertEqual(result["yield_loss_potential"], 50.0)


class TestGetPestCropInteractions(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_interactions(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("pest_name",), ("crop_name",), ("damage_type",),
            ("severity_by_stage",), ("yield_loss_potential",),
            ("peak_risk_stage",), ("preferred_management",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("fall_armyworm", "maize", "leaf_defoliation", {}, 50.0, "tasseling", []),
        ]
        result = get_pest_crop_interactions(self.conn, crop_name="maize")
        self.assertEqual(result["total"], 1)


class TestRecommendManagementForCrop(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_recommendations(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("pest_name",), ("damage_type",), ("severity_by_stage",),
            ("yield_loss_potential",), ("preferred_management",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("fall_armyworm", "leaf_defoliation",
             {"vegetative": "moderate", "tasseling": "high"}, 50.0,
             ["biological", "chemical"]),
        ]
        result = recommend_management_for_crop(self.conn, "maize", "tasseling")
        self.assertEqual(result["pest_count"], 1)
        self.assertEqual(result["recommendations"][0]["stage_severity"], "high")


# ============================================================
# Phase 13B: Trap Monitoring Tests
# ============================================================

class TestAddTrap(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_trap_id(self):
        result = add_trap(
            self.conn, "loc-001", "FAW Trap 1", "pheromone",
        )
        self.assertIn("trap_id", result)
        self.assertIsNotNone(result["trap_id"])

    def test_records_trap_type(self):
        result = add_trap(
            self.conn, "loc-001", "Sticky Trap", "sticky",
        )
        self.assertEqual(result["trap_type"], "sticky")

    def test_commits(self):
        add_trap(self.conn, "loc-001", "Trap 1", "pheromone")
        self.conn.commit.assert_called_once()


class TestRecordTrapCatch(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_catch_id(self):
        result = record_trap_catch(self.conn, "trap-001", pest_count=15)
        self.assertIn("catch_id", result)
        self.assertIsNotNone(result["catch_id"])

    def test_records_pest_count(self):
        result = record_trap_catch(self.conn, "trap-001", pest_count=15)
        self.assertEqual(result["pest_count"], 15)

    def test_records_beneficial_count(self):
        result = record_trap_catch(
            self.conn, "trap-001", pest_count=10, beneficial_count=3,
        )
        self.assertEqual(result["beneficial_count"], 3)


class TestGetTrapTrends(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_trends(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("trap_name",), ("trap_type",), ("target_pest",),
            ("check_date",), ("pest_count",), ("beneficial_count",),
            ("bycatch_count",), ("trap_condition",),
        ])
        self.mock_cursor.fetchall.return_value = [
            ("Trap 1", "pheromone", "fall_armyworm",
             date(2026, 7, 1), 12, 2, 1, "good"),
        ]
        result = get_trap_trends(self.conn, "trap-001")
        self.assertEqual(result["total_pest_count"], 12)
        self.assertEqual(result["total_beneficial_count"], 2)

    def test_empty_trends(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("trap_name",), ("trap_type",), ("target_pest",),
            ("check_date",), ("pest_count",), ("beneficial_count",),
            ("bycatch_count",), ("trap_condition",),
        ])
        self.mock_cursor.fetchall.return_value = []
        result = get_trap_trends(self.conn, "trap-001")
        self.assertEqual(result["total_pest_count"], 0)


class TestCheckTrapThreshold(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_error_for_missing_trap(self):
        self.mock_cursor.fetchone.return_value = None
        result = check_trap_threshold(self.conn, "bad-trap")
        self.assertIn("error", result)

    def test_above_et_returns_intervention(self):
        self.mock_cursor.fetchone.side_effect = [
            ("fall_armyworm", "loc-001"),  # trap info
            (15,),  # latest catch
            (10.0, 20.0, "per_plant"),  # threshold
        ]
        result = check_trap_threshold(self.conn, "trap-001")
        self.assertEqual(result["action"], "intervention_recommended")

    def test_below_et_returns_continue(self):
        self.mock_cursor.fetchone.side_effect = [
            ("fall_armyworm", "loc-001"),
            (5,),
            (10.0, 20.0, "per_plant"),
        ]
        result = check_trap_threshold(self.conn, "trap-001")
        self.assertEqual(result["action"], "continue_monitoring")

    def test_no_threshold_returns_monitor(self):
        self.mock_cursor.fetchone.side_effect = [
            ("fall_armyworm", "loc-001"),
            (10,),
            None,
        ]
        result = check_trap_threshold(self.conn, "trap-001")
        self.assertEqual(result["action"], "monitor")


# ============================================================
# Phase 13B: MoA Rotation Tests
# ============================================================

class TestAddModeOfAction(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_moa_id(self):
        result = add_mode_of_action(
            self.conn, "pyrethroid", "3A", "Sodium channel modulation",
        )
        self.assertIn("moa_id", result)
        self.assertIsNotNone(result["moa_id"])

    def test_records_class(self):
        result = add_mode_of_action(
            self.conn, "pyrethroid", "3A", "Sodium channel modulation",
        )
        self.assertEqual(result["chemical_class"], "pyrethroid")

    def test_records_code(self):
        result = add_mode_of_action(
            self.conn, "pyrethroid", "3A", "Sodium channel modulation",
        )
        self.assertEqual(result["moa_code"], "3A")


class TestCheckRotation(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_no_previous_returns_ok(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("application_date",), ("product_name",),
        ])
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.side_effect = [
            None,  # moa lookup
            None,  # previous class
        ]
        result = check_rotation(self.conn, "loc-001", "pyrethroid")
        self.assertTrue(result["rotation_ok"])

    def test_same_class_returns_not_ok(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("application_date",), ("product_name",),
        ])
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 7, 1), "Bt spray"),
        ]
        self.mock_cursor.fetchone.side_effect = [
            None,  # moa lookup
            ("pyrethroid",),  # previous class
        ]
        result = check_rotation(self.conn, "loc-001", "pyrethroid")
        self.assertFalse(result["rotation_ok"])
        self.assertIn("recommendation", result)

    def test_different_class_returns_ok(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("application_date",), ("product_name",),
        ])
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 6, 1), "Bt spray"),
        ]
        self.mock_cursor.fetchone.side_effect = [
            (None, None, None),  # moa lookup with no cross-resistance
            ("bioinsecticide",),  # previous class
        ]
        result = check_rotation(self.conn, "loc-001", "pyrethroid")
        self.assertTrue(result["rotation_ok"])


class TestGetRotationHistory(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_history(self):
        type(self.mock_cursor).description = PropertyMock(return_value=[
            ("application_date",), ("chemical_class",), ("product_name",),
            ("active_ingredient",),
        ])
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 6, 1), "pyrethroid", "Karate", "lambda-cyhalothrin"),
            (date(2026, 7, 1), "bioinsecticide", "Bt", "Bacillus thuringiensis"),
        ]
        result = get_rotation_history(self.conn, "loc-001")
        self.assertEqual(result["total_applications"], 2)
        self.assertIn("pyrethroid", result["unique_classes_used"])


# ============================================================
# Phase 13B: Spray Window Tests
# ============================================================

class TestGetOptimalSprayWindows(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_windows(self):
        self.mock_cursor.fetchone.side_effect = [
            ("larva", 200.0),  # degree day
            (1.0, 2.0),       # threshold
        ]
        self.mock_cursor.fetchall.return_value = [
            (date(2026, 7, 15), "suitable"),
            (date(2026, 7, 16), "marginal"),
        ]
        result = get_optimal_spray_windows(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(result["windows_ahead"], 2)
        self.assertEqual(result["current_lifecycle_stage"], "larva")

    def test_no_forecast_returns_empty(self):
        self.mock_cursor.fetchone.side_effect = [
            ("egg", 50.0),
            None,
        ]
        self.mock_cursor.fetchall.return_value = []
        result = get_optimal_spray_windows(self.conn, "loc-001", "fall_armyworm")
        self.assertEqual(result["windows_ahead"], 0)


# ============================================================
# Phase 13C: Organic Pest Score Tests
# ============================================================

class TestComputeOrganicPestScore(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_returns_score_components(self):
        self.mock_cursor.fetchone.side_effect = [
            (5,),   # bio count
            (2,),   # chem count
            (10,),  # chem total
            (3,),   # chem second half
            (5,),   # scouts
            (1,),   # schedules
        ]
        self.mock_cursor.fetchall.return_value = [
            ("biological",), ("chemical",),
        ]
        result = compute_organic_pest_score(self.conn, "loc-001")
        self.assertIn("organic_pest_score", result)
        self.assertIn("biocontrol_ratio_score", result)
        self.assertIn("chemical_reduction_score", result)

    def test_score_range(self):
        self.mock_cursor.fetchone.side_effect = [
            (0,), (0,), (0,), (0,), (5,), (0,),
        ]
        self.mock_cursor.fetchall.return_value = []
        result = compute_organic_pest_score(self.conn, "loc-001")
        score = result["organic_pest_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)


# ============================================================
# Phase 13C: IPM Audit Tests
# ============================================================

class TestGenerateIpmAudit(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    @unittest.mock.patch('services.analytics.pest_management.compute_ipm_compliance_score')
    @unittest.mock.patch('services.analytics.pest_management.check_rotation')
    def test_returns_audit(self, mock_rotation, mock_compliance):
        mock_compliance.return_value = {"overall_compliance_score": 75.0}
        mock_rotation.return_value = {"rotation_ok": True}

        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("intervention_type",), ("count",), ("avg_effectiveness",)],
            [("chemical_class",), ("product_name",), ("total_vol",), ("apps",)],
            [("intervention_type",)],
        ])
        self.mock_cursor.fetchone.side_effect = [
            (10, 2),  # scouts
            (0,),     # premature_chem
            (0,),     # resistance_alerts
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("biological", 5, 70.0), ("chemical", 3, 40.0)],
            [("pyrethroid", "Karate", 10.0, 3)],
            [("biological",), ("chemical",)],
        ]

        result = generate_ipm_audit(self.conn, "loc-001")
        self.assertIn("ipm_compliance_score", result)
        self.assertIn("scouting_summary", result)
        self.assertIn("intervention_summary", result)
        self.assertIn("chemical_summary", result)
        self.assertIn("findings", result)
        self.assertIn("overall_status", result)

    @unittest.mock.patch('services.analytics.pest_management.compute_ipm_compliance_score')
    @unittest.mock.patch('services.analytics.pest_management.check_rotation')
    def test_status_pass_when_no_findings(self, mock_rotation, mock_compliance):
        mock_compliance.return_value = {"overall_compliance_score": 90.0}
        mock_rotation.return_value = {"rotation_ok": True}

        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("intervention_type",), ("count",), ("avg_effectiveness",)],
            [("chemical_class",), ("product_name",), ("total_vol",), ("apps",)],
            [("intervention_type",)],
        ])
        self.mock_cursor.fetchone.side_effect = [
            (10, 0),  # scouts: 0 high severity
            (0,),     # premature_chem
            (0,),     # resistance_alerts
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("biological", 8, 80.0)],  # only biological
            [],                         # no chemicals
            [("biological",)],          # types
        ]

        result = generate_ipm_audit(self.conn, "loc-001")
        self.assertEqual(result["overall_status"], "pass")

    @unittest.mock.patch('services.analytics.pest_management.compute_ipm_compliance_score')
    @unittest.mock.patch('services.analytics.pest_management.check_rotation')
    def test_status_review_when_findings(self, mock_rotation, mock_compliance):
        mock_compliance.return_value = {"overall_compliance_score": 45.0}
        mock_rotation.return_value = {"rotation_ok": False, "recommendation": "Rotate classes"}

        type(self.mock_cursor).description = PropertyMock(side_effect=[
            [("intervention_type",), ("count",), ("avg_effectiveness",)],
            [("chemical_class",), ("product_name",), ("total_vol",), ("apps",)],
            [("intervention_type",)],
        ])
        self.mock_cursor.fetchone.side_effect = [
            (10, 5),  # scouts: 5 high severity (50% > 30%)
            (0,),     # premature_chem
            (2,),     # resistance_alerts
        ]
        self.mock_cursor.fetchall.side_effect = [
            [("biological", 2, 50.0), ("chemical", 8, 30.0)],
            [("pyrethroid", "Karate", 20.0, 5)],
            [("biological",), ("chemical",)],
        ]

        result = generate_ipm_audit(self.conn, "loc-001")
        self.assertEqual(result["overall_status"], "review_required")
        self.assertGreater(len(result["findings"]), 0)


if __name__ == "__main__":
    unittest.main()
