import pytest

from services.export.reports.commons.ecological import generate_ecological_modeling


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
def test_ecological_modeling_rejects_invalid_location_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without a location scope")

    with pytest.raises(
        ValueError,
        match="ecological_modeling requires an explicit location_id",
    ):
        generate_ecological_modeling(NoDatabase(), location_id)
