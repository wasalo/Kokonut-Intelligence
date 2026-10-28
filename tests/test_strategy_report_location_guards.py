"""Location-only strategy reports reject missing scope before database access."""

from unittest.mock import MagicMock

import pytest

from services.export.report_generator import NETWORK_LEVEL_REPORTS
from services.export.reports import REPORT_GENERATORS

LOCATION_REQUIRED_STRATEGY_REPORTS = (
    "business_model_canvas",
    "capital_accounting",
    "data_stream_summary",
    "env_scan_report",
    "fork_opportunities",
    "pestel_assessment",
    "pin_dependency",
    "pitch_deck",
    "promotion_ladder",
    "publics_market_landscape",
    "regional_readiness",
    "simulation_wargame",
    "stakeholder_decision_lineage",
    "stakeholder_engagement",
    "stakeholder_grievance",
    "stakeholder_landscape",
    "stakeholder_outcomes",
    "tactical_layer",
)


@pytest.mark.parametrize("report_type", LOCATION_REQUIRED_STRATEGY_REPORTS)
@pytest.mark.parametrize("location_id", [None, "", " ", "not-a-uuid", "all"])
def test_location_required_strategy_report_rejects_invalid_scope_before_database_access(
    report_type, location_id
):
    assert report_type in REPORT_GENERATORS
    assert report_type not in NETWORK_LEVEL_REPORTS
    conn = MagicMock()

    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        REPORT_GENERATORS[report_type](conn, location_id)

    conn.cursor.assert_not_called()
    conn.execute.assert_not_called()
