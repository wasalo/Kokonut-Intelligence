"""Portfolio analytics tests."""

from services.analytics.portfolio import confidence_label, ebf_portfolio_summary, portfolio_theme_summary


def test_confidence_label_thresholds() -> None:
    assert confidence_label(6, 2, 1) == "high"
    assert confidence_label(4, 1, 1) == "moderate"
    assert confidence_label(2, 1, 1) == "emerging"
    assert confidence_label(0, 0, 0) == "insufficient_evidence"


def test_portfolio_theme_summary_adds_confidence() -> None:
    class Cursor:
        def execute(self, query):
            pass

        def fetchall(self):
            return [{
                "theme_key": "8",
                "theme": "Decent Work and Economic Growth",
                "location_count": 1,
                "claim_count": 2,
                "avg_evidence_maturity": 5.5,
                "public_claim_count": 1,
                "level6_public_carbon_claim_count": 0,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = portfolio_theme_summary(Conn())
    assert result["theme_count"] == 1
    assert result["themes"][0]["confidence_label"] == "high"


def test_ebf_portfolio_summary_uses_messy_rollup_caveat() -> None:
    class Cursor:
        def execute(self, query):
            pass

        def fetchall(self):
            return [{
                "pillar_key": "soil_health",
                "pillar_name": "Soil Health",
                "location_count": 2,
                "scorecard_count": 2,
                "avg_score": 6.5,
                "avg_evidence_maturity": 4.5,
                "high_confidence_count": 0,
                "moderate_confidence_count": 2,
                "low_confidence_count": 0,
                "insufficient_evidence_count": 0,
                "public_safe_score_count": 2,
                "level6_carbon_score_count": 0,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = ebf_portfolio_summary(Conn())
    assert result["summary_type"] == "ebf_portfolio_messy_rollup"
    assert result["pillars"][0]["portfolio_confidence_label"] == "moderate"
    assert result["pillars"][0]["comparison_mode"] == "messy_rollup"
    assert "not interchangeable" in result["portfolio_caveat"]


if __name__ == "__main__":
    test_confidence_label_thresholds()
    test_portfolio_theme_summary_adds_confidence()
    test_ebf_portfolio_summary_uses_messy_rollup_caveat()
