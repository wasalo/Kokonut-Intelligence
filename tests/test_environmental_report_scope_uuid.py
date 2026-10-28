"""Environmental report scope is checked before opening a database cursor."""

import pytest

from services.export.reports.core import generate_environmental


class _NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("invalid scope must be rejected before cursor creation")


@pytest.mark.parametrize("location_id", [None, "", "all", "not-a-uuid"])
def test_environmental_report_rejects_non_uuid_scope_before_cursor(location_id):
    with pytest.raises(ValueError, match="explicit location_id"):
        generate_environmental(_NoDatabase(), location_id)
