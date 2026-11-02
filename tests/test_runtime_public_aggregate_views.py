"""Read-path contracts for the runtime-read-only public aggregate views."""

import re
import runpy
from contextlib import nullcontext
from pathlib import Path

from services.analytics import pitch, public_summary

ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _Connection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((" ".join(statement.split()), parameters))
        if statement.lstrip().upper().startswith("SET "):
            return _Result(None)
        return _Result(next(self.rows))


def test_public_location_summary_retains_attestation_aggregate_read(monkeypatch):
    location_id = "a0000000-0000-4000-8000-000000000001"
    location = {
        "id": location_id,
        "name": "Kokonut Adelphi",
        "country": "DO",
        "region": None,
        "status": "active",
    }
    metrics = {"metric_count": 2, "latest_computed_at": "2026-10-30T12:00:00Z"}
    attestations = {
        "total_attestations": 3,
        "published_count": 2,
        "latest_attestation": "2026-10-30T11:00:00Z",
    }
    connection = _Connection([location, metrics, attestations])
    monkeypatch.setattr(
        public_summary, "get_connection", lambda **_kwargs: nullcontext(connection)
    )

    result = public_summary.location_summary(location_id)

    assert result == {
        "summary_type": "public_location_summary",
        "location_id": location_id,
        "location": location,
        "metrics": metrics,
        "attestations": attestations,
    }
    attestation_query, parameters = next(
        call
        for call in connection.calls
        if "v_public_attestation_summary" in call[0]
    )
    assert (
        "FROM public.v_public_attestation_summary WHERE location_id = :location_id"
        in attestation_query
    )
    assert "SUM(total_attestations)" in attestation_query
    assert "SUM(published_count)" in attestation_query
    assert parameters == {"location_id": location_id}


def test_pitch_attestation_projection_remains_read_only_and_location_scoped():
    location_id = "a0000000-0000-4000-8000-000000000001"
    row = {
        "claim_type": "soil",
        "chain": "celo",
        "total_attestations": 3,
        "published_count": 2,
        "first_attestation": "2026-10-29T10:00:00Z",
        "latest_attestation": "2026-10-30T11:00:00Z",
    }

    class Cursor:
        def __init__(self):
            self.statement = None
            self.parameters = None

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, statement, parameters):
            self.statement = " ".join(statement.split())
            self.parameters = parameters

        def fetchall(self):
            return [row]

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, **_kwargs):
            return self.cursor_value

    connection = Connection()

    assert pitch._query_attestations(connection, location_id) == [row]
    assert connection.cursor_value.statement == (
        "SELECT claim_type, chain, total_attestations, published_count, "
        "first_attestation, latest_attestation "
        "FROM v_public_attestation_summary WHERE location_id = %s"
    )
    assert connection.cursor_value.parameters == (location_id,)


def test_targeted_aggregate_views_are_grouped_and_not_mutation_sources():
    attestation_ddl = (
        ROOT / "schemas/postgres/018_public_views.sql"
    ).read_text().lower()
    ebf_ddl = (ROOT / "schemas/postgres/032_ebf_scorecard.sql").read_text().lower()

    attestation_match = re.search(
        r"create or replace view v_public_attestation_summary\s+as(.*?);",
        attestation_ddl,
        re.DOTALL,
    )
    assert attestation_match is not None
    attestation_view = attestation_match.group(1)
    assert "group by" in attestation_view
    for view_name in (
        "v_public_ebf_scorecard_summary",
        "v_public_ebf_pillar_summary",
    ):
        view_start = ebf_ddl.index(f"create or replace view {view_name}")
        body_start = ebf_ddl.index("\nselect", view_start)
        next_view = ebf_ddl.find("\ncreate or replace view ", body_start)
        schema_version = ebf_ddl.find("\ninsert into schema_version", body_start)
        end_candidates = [position for position in (next_view, schema_version) if position >= 0]
        view = ebf_ddl[body_start : min(end_candidates)]
        assert "group by" in view
        assert "count(" in view or "avg(" in view

    report = runpy.run_path(
        str(ROOT / "scripts/runtime-privilege-callsite-report.py"),
        run_name="runtime_aggregate_view_policy_test",
    )
    for view_name in (
        "v_public_attestation_summary",
        "v_public_ebf_scorecard_summary",
        "v_public_ebf_pillar_summary",
    ):
        assert (
            report["_SOURCE_REVOKE_POLICY_OVERRIDES"][view_name]
            == "runtime_mutations_denied"
        )
