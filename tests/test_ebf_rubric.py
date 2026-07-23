"""EBF rubric band assignment tests."""

from pathlib import Path

from services.scoring.rubric import assign_default_band, band_label_for_score


def test_default_rubric_band_assignment() -> None:
    assert band_label_for_score(0) == "insufficient"
    assert band_label_for_score(2) == "emerging"
    assert band_label_for_score(4) == "developing"
    assert band_label_for_score(6) == "strong"
    assert band_label_for_score(9) == "leading"
    assert assign_default_band(9.8).score_value == 9


def test_seed_generates_70_default_bands() -> None:
    text = Path("schemas/seeds/032_ebf_rubric.sql").read_text().lower()
    assert "cross join generate_series(0, 9)" in text


def test_assign_default_band_at_boundaries() -> None:
    band_0 = assign_default_band(0.0)
    assert band_0.score_value == 0
    assert band_0.band_label == "insufficient"
    band_9 = assign_default_band(10.0)
    assert band_9.score_value == 10
    assert band_9.band_label == "leading"


def test_band_label_transitions() -> None:
    assert band_label_for_score(1.5) == "insufficient"
    assert band_label_for_score(2.0) == "emerging"
    assert band_label_for_score(4.0) == "developing"
    assert band_label_for_score(6.0) == "strong"
    assert band_label_for_score(8.0) == "leading"


def test_assign_default_band_clamps_out_of_range() -> None:
    band = assign_default_band(-3.0)
    assert band.score_value == 0
    band = assign_default_band(15.0)
    assert band.score_value == 10


if __name__ == "__main__":
    test_default_rubric_band_assignment()
    test_seed_generates_70_default_bands()
