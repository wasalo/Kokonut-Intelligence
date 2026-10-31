"""Direct-call scope validation for the location-specific wellbeing report."""

import pytest

from services.export.reports.wellbeing import generate_holistic_wellbeing


@pytest.mark.parametrize(
    "location_id",
    [None, "", "all", "not-a-uuid", "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222"],
)
def test_holistic_wellbeing_rejects_non_location_scope_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without one valid location scope")

    with pytest.raises(ValueError, match="holistic_wellbeing requires an explicit location_id"):
        generate_holistic_wellbeing(NoDatabase(), location_id)
