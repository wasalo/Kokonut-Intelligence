"""Wellbeing reports reject malformed location scope before cursor creation."""

import pytest

from services.export.reports import wellbeing

_LOCATION_REPORTS = [
    wellbeing.generate_ebf_scorecard,
    wellbeing.generate_financial_sustainability,
    wellbeing.generate_risk_mitigation,
    wellbeing.generate_scaling_roadmap,
    wellbeing.generate_capital_efficiency,
    wellbeing.generate_governance_throughput,
]


class _NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("invalid scope must be rejected before cursor creation")


@pytest.mark.parametrize("report", _LOCATION_REPORTS)
@pytest.mark.parametrize("location_id", [None, "", "all", "not-a-uuid"])
def test_location_reports_reject_non_uuid_scope_before_cursor(report, location_id):
    with pytest.raises(ValueError, match="explicit location_id"):
        report(_NoDatabase(), location_id)
