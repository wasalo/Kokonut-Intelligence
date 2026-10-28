import pytest

from services.export.reports.wellbeing import generate_ebf_scorecard


@pytest.mark.parametrize("location_id", [None, ""])
def test_ebf_scorecard_rejects_missing_location_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without a location scope")

    with pytest.raises(ValueError, match="ebf_scorecard requires an explicit location_id"):
        generate_ebf_scorecard(NoDatabase(), location_id)
