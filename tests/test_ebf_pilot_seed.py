"""Governance checks for the canonical Adelphi EBF pilot fixture."""

from pathlib import Path


SEED = Path("schemas/seeds/111_pilot_ebf_scorecard.sql")


def test_adelphi_ebf_pilot_seed_is_an_idempotent_draft_shell() -> None:
    text = SEED.read_text()
    assert "a0000000-0000-0000-0000-000001110001" in text
    assert "a0000000-0000-0000-0000-000000000001" in text
    assert "a0000000-0000-0000-0000-000000000010" in text
    assert "'insufficient_evidence'" in text
    assert "'draft'" in text
    assert "'2026.1'" in text
    assert "evidence_maturity_level" in text
    assert "public_claim_allowed" in text
    assert "ON CONFLICT (id) DO UPDATE SET" in text


def test_adelphi_ebf_pilot_seed_does_not_fabricate_scores_or_evidence() -> None:
    text = SEED.read_text().lower()
    assert "overall_score,\n    overall_confidence" in text
    assert "null,\n    'insufficient_evidence'" in text
    assert "insert into ebf_score (" not in text
    assert "insert into ebf_score_evidence (" not in text
    assert "public_claim_allowed, reviewer_notes, metadata" in text
    assert "    false,\n    'draft fixture pending" in text


if __name__ == "__main__":
    test_adelphi_ebf_pilot_seed_is_an_idempotent_draft_shell()
    test_adelphi_ebf_pilot_seed_does_not_fabricate_scores_or_evidence()
