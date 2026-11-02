"""Bio-factory reports reject invalid location scope before cursor access."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.export.reports.commons import bio_factory

LOCATION_ID = str(uuid4())
REPORTS = [
    (bio_factory.generate_bio_factory_batch, 2),
    (bio_factory.generate_bio_input_provenance, 2),
    (bio_factory.generate_bio_recipe_library, 1),
    (bio_factory.generate_bio_quality_test, 2),
]


@pytest.mark.parametrize("generator, _execute_count", REPORTS)
@pytest.mark.parametrize(
    "location_id",
    [None, "", "all", "not-a-uuid", f"{LOCATION_ID},{LOCATION_ID}"],
)
def test_malformed_or_missing_location_fails_before_cursor(
    generator, _execute_count, location_id
):
    conn = Mock()

    with pytest.raises(ValueError, match="requires an explicit location_id"):
        generator(conn, location_id)

    conn.cursor.assert_not_called()


@pytest.mark.parametrize("generator, execute_count", REPORTS)
def test_valid_location_keeps_existing_query_dispatch(generator, execute_count):
    conn = Mock()
    cursor = Mock()
    cursor.fetchone.return_value = {"name": "Synthetic farm"}
    cursor.fetchall.return_value = []
    conn.cursor.return_value = cursor

    report = generator(conn, LOCATION_ID)

    assert report["location_id"] == LOCATION_ID
    assert report["report_type"]
    conn.cursor.assert_called_once()
    assert cursor.execute.call_count == execute_count
    cursor.close.assert_called_once()
