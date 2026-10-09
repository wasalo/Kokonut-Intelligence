"""Tests for shared scoring normalization helpers (services.scoring.normalization)."""

from __future__ import annotations

import pytest

from services.scoring.normalization import clamp, clamp_score, weighted_score


def test_clamp_bounds_and_passthrough():
    assert clamp(150) == 100.0
    assert clamp(-5) == 0.0
    assert clamp(42.5) == 42.5
    assert clamp(42.5, minimum=20.0) == 42.5
    assert clamp(10.0, minimum=20.0) == 20.0
    assert clamp(200.0, maximum=50.0) == 50.0


def test_clamp_score_ebf_range_rounds():
    assert clamp_score(150) == 10.0
    assert clamp_score(-3) == 0.0
    assert clamp_score(7.56) == 7.6


def test_weighted_score_combines():
    result = weighted_score(
        {"a": 100.0, "b": 50.0},
        {"a": 0.25, "b": 0.75},
    )
    assert result == 62.5


def test_weighted_score_requires_matching_keys():
    with pytest.raises(ValueError):
        weighted_score({"a": 1.0}, {"a": 0.5, "b": 0.5})
    with pytest.raises(ValueError):
        weighted_score({"a": 1.0, "b": 2.0}, {"a": 1.0})
