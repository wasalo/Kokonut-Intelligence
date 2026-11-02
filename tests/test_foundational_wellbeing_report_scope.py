"""Direct-call scope validation for foundational-wellbeing reports."""

import pytest

from services.export.reports.commons.wellbeing import generate_foundational_wellbeing


class NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("database access must not occur for invalid location scope")


@pytest.mark.parametrize(
    "location_id",
    [
        None,
        "",
        "all",
        "not-a-uuid",
        "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
    ],
)
def test_foundational_wellbeing_rejects_invalid_location_before_database_access(location_id):
    with pytest.raises(
        ValueError,
        match="foundational_wellbeing requires an explicit location_id",
    ):
        generate_foundational_wellbeing(NoDatabase(), location_id)
