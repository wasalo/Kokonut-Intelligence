"""Tests for Cross-Domain Insight Transfer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestInsightTransferEngine:
    def _make_engine(self):
        from services.events.insight_transfer import InsightTransferEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return InsightTransferEngine(conn=mock_conn), mock_conn, mock_cursor

    def test_process_event_no_rules(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.process_event("pest", "outbreak", {"severity": "high"})

        assert isinstance(result, list)
        assert len(result) == 0

    def test_process_event_with_rule(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "source_domain": "pest",
                "target_domain": "irrigation",
                "source_event_pattern": "outbreak",
                "target_action_template": {"action": "adjust_irrigation"},
                "confidence": 0.7,
                "enabled": True,
            }
        ]

        result = engine.process_event("pest", "outbreak", {"severity": "high"})

        assert len(result) == 1
        assert result[0]["target_domain"] == "irrigation"
        assert result[0]["applicability"] == 0.7

    def test_process_event_persists_transfer(self):
        engine, mock_conn, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "source_domain": "weather",
                "target_domain": "planting",
                "source_event_pattern": "frost_warning",
                "target_action_template": {"action": "delay_planting"},
                "confidence": 0.9,
                "enabled": True,
            }
        ]

        engine.process_event("weather", "frost_warning", {})

        # Should have INSERT call for insight_transfer
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("insight_transfer" in c for c in calls)

    def test_add_rule_returns_id(self):
        engine, _, mock_cursor = self._make_engine()

        result = engine.add_rule(
            "pest", "irrigation", "outbreak",
            {"action": "adjust"}, confidence=0.6
        )

        assert "id" in result
        assert result["source_domain"] == "pest"
        assert result["confidence"] == 0.6

    def test_get_pending_transfers_returns_list(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.get_pending_transfers()

        assert isinstance(result, list)

    def test_get_transfer_stats_empty(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.get_transfer_stats()

        assert result["total_transfers"] == 0
        assert result["domain_pairs"] == []

    def test_get_transfer_stats_with_data(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "source_domain": "pest",
                "target_domain": "irrigation",
                "total_transfers": 10,
                "helpful": 7,
                "not_helpful": 2,
                "pending": 1,
                "avg_applicability": 0.65,
            }
        ]

        result = engine.get_transfer_stats()

        assert result["total_transfers"] == 10
        assert result["domain_pairs"][0]["effectiveness_rate"] == 70.0

    def test_get_rules_returns_list(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.get_rules()

        assert isinstance(result, list)

    def test_resolve_transfer_updates_outcome(self):
        engine, mock_conn, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "source_domain": "pest",
            "source_event_type": "outbreak",
            "outcome": "helpful",
        }
        mock_cursor.fetchall.return_value = [
            {"total": 5, "helpful": 3}
        ]

        result = engine.resolve_transfer(str(uuid.uuid4()), "helpful")

        assert result["outcome"] == "helpful"

    def test_process_event_multiple_rules(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "source_domain": "weather",
                "target_domain": "irrigation",
                "source_event_pattern": "heavy_rain",
                "target_action_template": {"action": "skip_irrigation"},
                "confidence": 0.8,
                "enabled": True,
            },
            {
                "id": str(uuid.uuid4()),
                "source_domain": "weather",
                "target_domain": "planting",
                "source_event_pattern": "heavy_rain",
                "target_action_template": {"action": "delay_planting"},
                "confidence": 0.5,
                "enabled": True,
            },
        ]

        result = engine.process_event("weather", "heavy_rain", {})

        assert len(result) == 2
        domains = {r["target_domain"] for r in result}
        assert "irrigation" in domains
        assert "planting" in domains
