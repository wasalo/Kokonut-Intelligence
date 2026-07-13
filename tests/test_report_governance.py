"""Governance checks for generated report snapshots."""

import inspect

from services.export.report_generator import store_snapshot


def test_generated_report_snapshot_starts_as_unfrozen_draft() -> None:
    source = inspect.getsource(store_snapshot)
    assert "'draft', FALSE, NULL" in source
    assert "'published', TRUE" not in source
