"""Best-effort metric event publishing must not log database diagnostics."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from services.metrics import engine


def test_metric_event_publication_failure_is_redacted_and_best_effort(caplog):
    bus = MagicMock()
    bus.publish.side_effect = RuntimeError("postgresql://operator:secret@db.internal/kokonut")
    with (
        patch.object(engine, "_get_event_bus", return_value=bus),
        caplog.at_level(logging.ERROR, logger="kokonut.services.metrics.engine"),
    ):
        engine._publish_metric_event(
            MagicMock(),
            "sensitive-location-id",
            "2026-01-01",
            "2026-01-31",
            {"total_computed": 1, "computed": {"soil": {}}},
        )

    bus.publish.assert_called_once()
    assert "postgresql://operator:secret" not in caplog.text
    assert "sensitive-location-id" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert "Traceback" not in caplog.text
