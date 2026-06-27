"""EBF carbon claim restriction tests."""

from pathlib import Path

from services.scoring.gates import linked_carbon_claim_allowed, public_carbon_score_allowed


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")


def test_public_carbon_score_requires_level6() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_score_public_carbon_level6" in text
    assert "pillar_key = 'carbon_sequestration'" in text
    assert "evidence_maturity_level = 6" in text


def test_service_carbon_gate_requires_level6_and_evidence() -> None:
    assert public_carbon_score_allowed(6, True) is True
    assert public_carbon_score_allowed(5, True) is False
    assert public_carbon_score_allowed(6, False) is False


def test_linked_carbon_claim_requires_verifier_and_methodology() -> None:
    valid = {
        "claim_category": "carbon",
        "claim_type": "third_party_verified_claim",
        "evidence_maturity": 6,
        "status": "published",
        "external_verifier": "External MRV reviewer",
        "methodology_ref": "IPCC 2006 GHG Guidelines",
    }
    assert linked_carbon_claim_allowed(valid) is True
    invalid = {**valid, "methodology_ref": ""}
    assert linked_carbon_claim_allowed(invalid) is False


if __name__ == "__main__":
    test_public_carbon_score_requires_level6()
    test_service_carbon_gate_requires_level6_and_evidence()
    test_linked_carbon_claim_requires_verifier_and_methodology()
