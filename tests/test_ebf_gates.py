"""EBF evidence maturity gate tests."""

from pathlib import Path


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")


def test_public_scorecard_requires_level4_and_public_claim_allowed() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_scorecard_public_maturity" in text
    assert "evidence_maturity_level >= 4" in text
    assert "public_claim_allowed = true" in text


def test_public_scores_require_evidence_links_in_view() -> None:
    text = SCHEMA.read_text().lower()
    assert "select 1 from ebf_score_evidence" in text
    assert "es.public_score_allowed = true" in text


if __name__ == "__main__":
    test_public_scorecard_requires_level4_and_public_claim_allowed()
    test_public_scores_require_evidence_links_in_view()
