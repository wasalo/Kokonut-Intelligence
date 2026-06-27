"""EBF carbon claim restriction tests."""

from pathlib import Path


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")


def test_public_carbon_score_requires_level6() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_score_public_carbon_level6" in text
    assert "pillar_key = 'carbon_sequestration'" in text
    assert "evidence_maturity_level = 6" in text


if __name__ == "__main__":
    test_public_carbon_score_requires_level6()
