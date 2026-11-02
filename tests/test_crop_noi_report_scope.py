"""Direct-call scope validation for the location-specific crop NOI report."""

import pytest

from services.export.reports.core import generate_crop_noi


@pytest.mark.parametrize(
    "location_id",
    [None, "", "all", "not-a-uuid", "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222"],
)
def test_crop_noi_rejects_non_location_scope_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without one valid location scope")

    with pytest.raises(ValueError, match="crop_noi requires an explicit location_id"):
        generate_crop_noi(NoDatabase(), location_id)
