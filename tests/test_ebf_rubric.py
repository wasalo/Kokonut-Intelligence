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


if __name__ == "__main__":
    test_default_rubric_band_assignment()
    test_seed_generates_70_default_bands()
