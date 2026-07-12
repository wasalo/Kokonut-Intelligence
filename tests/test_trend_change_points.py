"""Tests for Change-Point Detector."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestChangePointDetector:
    def _make_detector(self):
        from services.trends.change_points import ChangePointDetector
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return ChangePointDetector(conn=mock_conn), mock_conn, mock_cursor

    def test_cusum_detect_finds_change(self):
        detector, _, _ = self._make_detector()
        # Series with a clear shift
        series = [5.0] * 20 + [15.0] * 20
        result = detector.cusum_detect(series)
        assert len(result["change_points"]) > 0

    def test_cusum_detect_no_change_in_stable(self):
        detector, _, _ = self._make_detector()
        series = [5.0] * 30
        result = detector.cusum_detect(series)
        assert len(result["change_points"]) == 0

    def test_cusum_detect_insufficient_data(self):
        detector, _, _ = self._make_detector()
        result = detector.cusum_detect([1.0, 2.0])
        assert result["change_points"] == []

    def test_pelt_detect_finds_multiple_changes(self):
        detector, _, _ = self._make_detector()
        series = [5.0] * 10 + [15.0] * 10 + [5.0] * 10
        result = detector.pelt_detect(series)
        assert len(result["change_points"]) >= 1

    def test_pelt_detect_insufficient_data(self):
        detector, _, _ = self._make_detector()
        result = detector.pelt_detect([1.0, 2.0])
        assert result["change_points"] == []

    def test_classify_change_level_shift(self):
        detector, _, _ = self._make_detector()
        old = [5.0, 5.0, 5.0]
        new = [15.0, 15.0, 15.0]
        result = detector.classify_change(old, new)
        assert result == "level_shift"

    def test_classify_change_unknown_with_empty(self):
        detector, _, _ = self._make_detector()
        result = detector.classify_change([], [1.0])
        assert result == "unknown"

    def test_build_segments_returns_segments(self):
        detector, _, _ = self._make_detector()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        segments = detector._build_segments(series, [2])
        assert len(segments) == 2
        assert segments[0]["start_index"] == 0
        assert segments[1]["end_index"] == 5

    def test_merge_change_points_deduplicates(self):
        detector, _, _ = self._make_detector()
        points = [
            {"index": 10, "magnitude": 5.0, "direction": "increase"},
            {"index": 12, "magnitude": 3.0, "direction": "increase"},
            {"index": 25, "magnitude": 7.0, "direction": "decrease"},
        ]
        merged = detector._merge_change_points(points, tolerance=5)
        assert len(merged) == 2

    def test_cusum_segments_built(self):
        detector, _, _ = self._make_detector()
        series = [5.0] * 10 + [15.0] * 10
        result = detector.cusum_detect(series)
        assert len(result["segments"]) >= 1
