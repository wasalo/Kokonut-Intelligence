import pytest

from services.export.reports.commons.stewardship import generate_regenerative_outcomes


class NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("database access must not occur for an invalid location scope")


@pytest.mark.parametrize(
    "location_id",
    [None, "", " ", "not-a-uuid", "all", "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222"],
)
def test_regenerative_outcomes_rejects_invalid_location_before_database_access(location_id):
    with pytest.raises(ValueError, match="regenerative_outcomes requires an explicit location_id"):
        generate_regenerative_outcomes(NoDatabase(), location_id)
