import pytest

from services.export.reports.core import generate_environmental


@pytest.mark.parametrize("location_id", [None, ""])
def test_environmental_report_rejects_missing_location_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without a location scope")

    with pytest.raises(ValueError, match="environmental requires an explicit location_id"):
        generate_environmental(NoDatabase(), location_id)
