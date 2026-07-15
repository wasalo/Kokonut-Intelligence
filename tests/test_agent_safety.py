"""Agent safety helper tests."""

from services.agents.safety import (
    GOVERNED_COLLECTIONS,
    assess_agent_action,
    assert_agent_action_allowed,
    payload_hash,
)


def test_payload_hash_is_stable() -> None:
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})


def test_blocks_agent_publish_status() -> None:
    decision = assess_agent_action(
        "update", "agent_task", {"review_status": "published"}
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_high_risk_action_requires_human_approval() -> None:
    decision = assert_agent_action_allowed("attest", "attestation_request", {})
    assert decision.allowed is True
    assert decision.high_risk is True
    assert decision.requires_human_approval is True


def test_modeled_decision_outputs_are_governed() -> None:
    expected = {
        "report_snapshot",
        "forecast_scenario",
        "forecast_output",
        "crisp_risk_assessment",
        "threat_narrative",
        "backcast_path_comparison",
        "backcast_path_premortem",
        "prediction_ledger",
        "prediction_outcome",
        "reference_class",
        "outside_view_comparison",
        "delphi_minority_report",
        "threat_forecast_resolution",
    }
    assert expected <= GOVERNED_COLLECTIONS


def test_agent_cannot_publish_modeled_decision_output() -> None:
    decision = assess_agent_action(
        "update", "report_snapshot", {"status": "published"}
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_stakeholder_human_review_collections_are_write_protected() -> None:
    for collection in (
        "stakeholder_consent",
        "stakeholder_decision",
        "buyer_verification",
        "party_trust_evidence",
        "nature_stewardship_obligation",
    ):
        decision = assess_agent_action("create", collection, {})
        assert decision.allowed is False
        assert decision.requires_human_approval is True


def test_agent_can_read_stakeholder_records() -> None:
    decision = assess_agent_action("read", "stakeholder_decision", {})
    assert decision.allowed is True


if __name__ == "__main__":
    test_payload_hash_is_stable()
    test_blocks_agent_publish_status()
    test_high_risk_action_requires_human_approval()
