"""Batch-size validation happens before constructing stream workers or DB connections."""

from __future__ import annotations

import sys

import pytest

from services.stream.cli import main
from services.stream.processor import StreamProcessor


@pytest.mark.parametrize("batch_size", ["0", "-1", "501", "1000000", "not-an-int"])
def test_cli_rejects_invalid_batch_size_before_processor_construction(
    monkeypatch, batch_size
):
    constructions = []

    class UnexpectedProcessor:
        def __init__(self):
            constructions.append(True)
            pytest.fail("invalid batch size reached processor construction")

    monkeypatch.setattr("services.stream.processor.StreamProcessor", UnexpectedProcessor)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stream", "--run", "--batch-size", batch_size],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    assert constructions == []


@pytest.mark.parametrize("batch_size", [1, 500])
def test_cli_forwards_valid_batch_size_unchanged(monkeypatch, batch_size):
    forwarded = []

    class RecordingProcessor:
        def process_buffer(self, *, batch_size):
            forwarded.append(batch_size)
            return {"processed": 0, "aggregated": 0, "errors": 0}

    monkeypatch.setattr("services.stream.processor.StreamProcessor", RecordingProcessor)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stream", "--run", "--batch-size", str(batch_size)],
    )

    with pytest.raises(SystemExit) as result:
        main()

    assert result.value.code == 0
    assert forwarded == [batch_size]


@pytest.mark.parametrize("batch_size", [0, -1, 501, "1", 1.0, True])
def test_process_buffer_rejects_invalid_batch_size_before_database_access(
    monkeypatch, batch_size
):
    processor = StreamProcessor()

    def unexpected_database_access():
        pytest.fail("invalid batch size reached database acquisition")

    monkeypatch.setattr(processor, "_get_conn", unexpected_database_access)

    with pytest.raises(ValueError, match="batch_size"):
        processor.process_buffer(batch_size)
