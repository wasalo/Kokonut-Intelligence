"""CSW catalog query authorization and pagination boundaries."""

import pytest

from services.csw import get_record, get_records


class _Result:
    def __init__(self, matched=0):
        self.matched = matched

    def mappings(self):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def scalar_one(self):
        return self.matched


class _Connection:
    def __init__(self, matched=0):
        self.statements = []
        self.matched = matched

    def text(self, statement):
        return statement

    def execute(self, statement, parameters):
        self.statements.append((statement, parameters))
        if "SELECT COUNT(*)" in statement:
            return _Result(self.matched)
        return _Result()


def test_get_record_applies_the_same_public_visibility_filter_as_catalog_search():
    connection = _Connection()

    assert get_record(connection, "private-or-unknown-id") is None

    statement, parameters = connection.statements[0]
    assert "dsp.status IN ('published', 'verified')" in statement
    assert "dsp.visibility = 'public'" in statement
    assert parameters == {"rid": "private-or-unknown-id"}


@pytest.mark.parametrize(
    ("max_records", "start_position"),
    [
        (0, 1),
        (101, 1),
        (-1, 1),
        (1, 0),
        (1, -1),
        (True, 1),
    ],
)
def test_get_records_rejects_invalid_or_unbounded_pagination_before_query(
    max_records, start_position
):
    connection = _Connection()

    with pytest.raises(ValueError):
        get_records(
            connection,
            max_records=max_records,
            start_position=start_position,
        )

    assert connection.statements == []


def test_get_records_uses_public_filter_and_bounded_page():
    connection = _Connection(matched=243)

    result = get_records(connection, query="soil", max_records=100, start_position=3)

    count_statement, count_parameters = connection.statements[0]
    page_statement, page_parameters = connection.statements[1]
    assert "SELECT COUNT(*)" in count_statement
    assert "dsp.visibility = 'public'" in count_statement
    assert "dsp.visibility = 'public'" in page_statement
    assert count_parameters == {"q": "%soil%"}
    assert "LIMIT :limit OFFSET :offset" in page_statement
    assert page_parameters == {"q": "%soil%", "limit": 100, "offset": 2}
    assert result["searchResults"]["numberOfRecordsMatched"] == 243
    assert result["searchResults"]["numberOfRecordsReturned"] == 0
