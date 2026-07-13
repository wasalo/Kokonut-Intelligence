#!/usr/bin/env python3
"""
Tests for LLM Chat — Natural Language Interface
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.analytics.llm_chat import (
    classify_intent,
    _extract_entities,
    create_session,
    get_session,
    process_message,
    get_chat_history,
    list_intents,
    _handle_yield,
    _handle_weather,
    _handle_soil,
    _handle_crisp,
    _handle_advisory,
    _handle_cost,
    _format_intents,
    _format_history,
)


class TestIntentClassification(unittest.TestCase):

    def test_yield_intent(self):
        result = classify_intent("What is the maize yield this season?")
        self.assertEqual(result["intent"], "get_yield")
        self.assertGreater(result["confidence"], 0)

    def test_weather_intent(self):
        result = classify_intent("Will it rain tomorrow?")
        self.assertEqual(result["intent"], "get_weather")

    def test_soil_intent(self):
        result = classify_intent("What is the soil moisture level?")
        self.assertEqual(result["intent"], "get_soil")

    def test_crisp_intent(self):
        result = classify_intent("What is our CRISP risk score?")
        self.assertEqual(result["intent"], "get_crisp")

    def test_advisory_intent(self):
        result = classify_intent("What should I do today?")
        self.assertEqual(result["intent"], "get_advisory")

    def test_comparison_intent(self):
        result = classify_intent("How does this season compare to last?")
        self.assertEqual(result["intent"], "compare_seasons")

    def test_cost_intent(self):
        result = classify_intent("Estimate the fertilizer cost per hectare")
        self.assertEqual(result["intent"], "estimate_cost")

    def test_twin_intent(self):
        result = classify_intent("Simulate with more irrigation")
        self.assertEqual(result["intent"], "digital_twin")

    def test_unknown_intent(self):
        result = classify_intent("Tell me a joke")
        self.assertEqual(result["intent"], "unknown")
        self.assertEqual(result["confidence"], 0.0)


class TestEntityExtraction(unittest.TestCase):

    def test_crop_extraction(self):
        entities = _extract_entities("what was the maize yield?")
        self.assertEqual(entities["crop_name"], "maize")

    def test_crop_beans(self):
        entities = _extract_entities("show me the beans production")
        self.assertEqual(entities["crop_name"], "beans")

    def test_time_ref_last_season(self):
        entities = _extract_entities("yield last season")
        self.assertEqual(entities["time_ref"], "last_season")

    def test_time_ref_today(self):
        entities = _extract_entities("what is the weather today?")
        self.assertEqual(entities["time_ref"], "today")

    def test_area_extraction(self):
        entities = _extract_entities("cost for 5.5 ha")
        self.assertEqual(entities["area"], 5.5)

    def test_quantity_extraction(self):
        entities = _extract_entities("apply 120 kg of nitrogen")
        self.assertEqual(entities["quantity"], 120.0)
        self.assertEqual(entities["quantity_unit"], "kg")

    def test_metric_extraction(self):
        entities = _extract_entities("what is the soil moisture?")
        self.assertEqual(entities["metric"], "soil_moisture")


class TestSessionManagement(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = ("sess-001",)
        self.mock_cursor.description = [("id",)]

    def test_create_session(self):
        result = create_session(self.conn, "loc-001", "admin", "Test Chat")
        self.assertIn("session_id", result)
        self.assertEqual(result["location_id"], "loc-001")

    def test_get_session(self):
        self.mock_cursor.fetchone.return_value = (
            "sess-001", "loc-001", "admin", "Test Chat", "active", 5,
            datetime.now(timezone.utc),
        )
        self.mock_cursor.description = [
            ("id",), ("location_id",), ("user_id",), ("title",),
            ("status",), ("message_count",), ("started_at",),
        ]
        result = get_session(self.conn, "sess-001")
        self.assertEqual(result["session_id"], "sess-001")
        self.assertEqual(result["message_count"], 5)

    def test_get_session_not_found(self):
        self.mock_cursor.fetchone.return_value = None
        result = get_session(self.conn, "nonexistent")
        self.assertIn("error", result)


class TestMessageProcessing(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_process_message_unknown(self):
        result = process_message(self.conn, "sess-001", "Tell me a joke")
        self.assertIn("response", result)
        self.assertEqual(result["intent"], "unknown")

    def test_process_message_yield(self):
        from services.analytics import llm_chat
        with patch.object(llm_chat, '_handle_yield', return_value=(
            "The average maize yield is 2500 kg/ha.",
            ["harvest_yield_observation"],
            {"avg_yield": 2500.0},
        )):
            result = process_message(self.conn, "sess-001", "What is the current maize yield?")
            self.assertIn("response", result)
            self.assertEqual(result["intent"], "get_yield")


class TestIntentHandlers(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_handle_yield_no_data(self):
        self.mock_cursor.fetchone.return_value = (None, None, 0)
        response, sources, results = _handle_yield(self.conn, {}, "loc-001")
        self.assertIn("don't have", response)

    def test_handle_yield_with_data(self):
        self.mock_cursor.fetchone.return_value = (2500.0, 12500.0, 5)
        response, sources, results = _handle_yield(self.conn, {"crop_name": "maize"}, "loc-001")
        self.assertIn("2500", response)
        self.assertIn("maize", response)

    def test_handle_yield_no_location(self):
        response, sources, results = _handle_yield(self.conn, {}, None)
        self.assertIn("don't have", response)

    def test_handle_weather_no_data(self):
        self.mock_cursor.fetchone.return_value = (None, None, None, None)
        response, sources, results = _handle_weather(self.conn, {}, "loc-001")
        self.assertIn("not available", response)

    def test_handle_weather_with_data(self):
        self.mock_cursor.fetchone.return_value = (25.0, 5.0, 70.0, 10.0)
        response, sources, results = _handle_weather(self.conn, {}, "loc-001")
        self.assertIn("25", response)

    def test_handle_soil_no_data(self):
        self.mock_cursor.fetchone.return_value = (None,)
        response, sources, results = _handle_soil(self.conn, {}, "loc-001")
        self.assertIn("don't have", response)

    def test_handle_soil_with_data(self):
        self.mock_cursor.fetchone.return_value = (45.0,)
        response, sources, results = _handle_soil(self.conn, {"metric": "soil_moisture"}, "loc-001")
        self.assertIn("45", response)

    def test_handle_crisp_no_data(self):
        self.mock_cursor.fetchall.return_value = []
        response, sources, results = _handle_crisp(self.conn, {}, "loc-001")
        self.assertIn("don't have", response)

    def test_handle_crisp_with_data(self):
        self.mock_cursor.fetchall.return_value = [
            ("carbon_yield", 75, "AA"),
            ("climate", 60, "A"),
        ]
        response, sources, results = _handle_crisp(self.conn, {}, "loc-001")
        self.assertIn("CRISP", response)
        self.assertIn("carbon_yield", response)

    def test_handle_advisory_empty(self):
        self.mock_cursor.fetchall.return_value = []
        response, sources, results = _handle_advisory(self.conn, {}, "loc-001")
        self.assertIn("No pending", response)

    def test_handle_advisory_with_data(self):
        self.mock_cursor.fetchall.return_value = [
            ("Soil moisture low", "warning", "within_48h", "Check irrigation"),
            ("Frost alert", "critical", "immediate", "Protect crops"),
        ]
        response, sources, results = _handle_advisory(self.conn, {}, "loc-001")
        self.assertIn("2 pending", response)

    def test_handle_cost(self):
        response, sources, results = _handle_cost(self.conn, {"area": 5.0, "crop_name": "maize"}, None)
        self.assertIn("Estimated", response)
        self.assertIn("$", response)


class TestChatHistory(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_empty_history(self):
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.description = []
        result = get_chat_history(self.conn, "sess-001")
        self.assertEqual(result, [])

    def test_history_with_messages(self):
        self.mock_cursor.fetchall.return_value = [
            ("user", "What was the yield?", "get_yield", 0.8, datetime.now(timezone.utc)),
            ("assistant", "The average yield is 2500 kg/ha.", "get_yield", 0.8, datetime.now(timezone.utc)),
        ]
        self.mock_cursor.description = [
            ("role",), ("content",), ("intent",), ("intent_confidence",), ("created_at",),
        ]
        result = get_chat_history(self.conn, "sess-001")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")


class TestIntents(unittest.TestCase):

    def setUp(self):
        self.conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.conn.cursor.return_value = self.mock_cursor

    def test_list_intents(self):
        self.mock_cursor.fetchall.return_value = [
            ("get_yield", "Get yield data", '["What was the yield?"]', "low", "active"),
        ]
        self.mock_cursor.description = [
            ("name",), ("description",), ("examples",), ("risk_level",), ("status",),
        ]
        result = list_intents(self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "get_yield")


class TestFormatting(unittest.TestCase):

    def test_format_intents_empty(self):
        result = _format_intents([])
        self.assertEqual(result, "No intents registered.")

    def test_format_intents(self):
        result = _format_intents([
            {"name": "get_yield", "risk_level": "low", "description": "Get yield data for a crop or location"},
        ])
        self.assertIn("get_yield", result)

    def test_format_history_empty(self):
        result = _format_history([])
        self.assertEqual(result, "No messages.")

    def test_format_history(self):
        result = _format_history([
            {"role": "user", "content": "What was the yield?"},
            {"role": "assistant", "content": "The average yield is 2500 kg/ha."},
        ])
        self.assertIn("[You]", result)
        self.assertIn("[AI]", result)


if __name__ == "__main__":
    unittest.main()
