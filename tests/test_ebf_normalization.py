"""EBF score normalization tests."""

from services.scoring.normalization import clamp_score, normalize_linear, normalize_percentage


def test_clamp_score_bounds_values() -> None:
    assert clamp_score(-5) == 0.0
    assert clamp_score(11) == 10.0
    assert clamp_score(4.44) == 4.4


def test_linear_and_percentage_normalization() -> None:
    assert normalize_linear(50, 0, 100) == 5.0
    assert normalize_linear(25, 0, 100, invert=True) == 7.5
    assert normalize_percentage(80) == 8.0


def test_invalid_range_raises() -> None:
    try:
        normalize_linear(1, 1, 1)
    except ValueError as exc:
        assert "maximum" in str(exc)
    else:
        raise AssertionError("expected ValueError")


if __name__ == "__main__":
    test_clamp_score_bounds_values()
    test_linear_and_percentage_normalization()
    test_invalid_range_raises()
