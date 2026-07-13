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
    }
    assert expected <= GOVERNED_COLLECTIONS


def test_agent_cannot_publish_modeled_decision_output() -> None:
    decision = assess_agent_action(
        "update", "report_snapshot", {"status": "published"}
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


if __name__ == "__main__":
    test_payload_hash_is_stable()
    test_blocks_agent_publish_status()
    test_high_risk_action_requires_human_approval()
