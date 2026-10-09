"""Governance checks for generated report snapshots."""

import inspect

from services.export.report_generator import build_negative_findings, store_snapshot


def test_generated_report_snapshot_starts_as_unfrozen_draft() -> None:
    source = inspect.getsource(store_snapshot)
    assert "'draft', FALSE, NULL" in source
    assert "'published', TRUE" not in source


def test_cross_system_negative_findings_are_balanced() -> None:
    findings = build_negative_findings({
        "evidence_gaps": [],
        "forecast_performance": {"evaluated_count": 3, "overprediction_count": 2},
        "backcast_milestone_health": {"blocked_count": 1, "overdue_count": 1},
        "unresolved_assumption_challenges": {"pending_count": 1},
        "delphi_dissent": {"non_consensus_count": 1},
        "crisp_risk": {"composite_score": 75, "rating": "B", "confidence_level": "low"},
    })
    codes = {finding["code"] for finding in findings}
    assert "FORECAST_OVERPREDICTION" in codes
    assert "BACKCAST_BLOCKED_MILESTONES" in codes
    assert "BACKCAST_PENDING_ASSUMPTIONS" in codes
    assert "DELPHI_NON_CONSENSUS" in codes
    assert "CRISP_HIGH_RISK" in codes
    assert "CRISP_INSUFFICIENT_EVIDENCE" in codes
    assert all(finding.get("review_prompt") for finding in findings)


def test_no_data_does_not_create_false_findings() -> None:
    assert build_negative_findings({"evidence_gaps": []}) == []


def test_report_context_uses_public_safe_modeled_views() -> None:
    from services.export.report_generator import fetch_public_interest_context
    source = inspect.getsource(fetch_public_interest_context)
    assert "v_public_prediction_accuracy" in source
    assert "v_delphi_consensus_public" in source
    assert "v_crisp_composite_rating" in source
    assert "predicted_value - actual_value" in source
    assert "This is not evidence that adverse outcomes" in source
