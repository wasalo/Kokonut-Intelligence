"""Portfolio analytics tests."""

from services.analytics.portfolio import confidence_label, portfolio_theme_summary


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


if __name__ == "__main__":
    test_confidence_label_thresholds()
    test_portfolio_theme_summary_adds_confidence()
