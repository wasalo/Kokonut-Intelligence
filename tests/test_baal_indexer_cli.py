"""Offline standalone/unified parser contracts for the Baal indexer."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.ingestion import baal_indexer
from services.ingestion import cli as ingestion_cli


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], {"from_block": None, "to_block": None}),
        (
            ["--from-block", "29810566", "--to-block", "29810570"],
            {"from_block": 29810566, "to_block": 29810570},
        ),
    ],
)
def test_standalone_and_unified_entrypoints_forward_block_interval(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected: dict[str, int | None],
) -> None:
    calls: list[dict[str, int | None]] = []
    monkeypatch.setattr(baal_indexer, "run", lambda **kwargs: calls.append(kwargs))

    baal_indexer.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["baal_indexer", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == expected


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--from-block", "-1"], "--from-block must be non-negative"),
        (["--to-block", "-1"], "--to-block must be non-negative"),
        (
            ["--from-block", "10", "--to-block", "9"],
            "--to-block must be greater than or equal",
        ),
    ],
)
@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_invalid_block_interval_fails_before_provider_or_database(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    message: str,
    unified: bool,
) -> None:
    monkeypatch.setattr(
        baal_indexer,
        "Web3",
        lambda *_args, **_kwargs: pytest.fail("invalid range reached provider"),
    )
    monkeypatch.setattr(
        baal_indexer, "get_db", lambda: pytest.fail("invalid range opened database")
    )

    with pytest.raises(SystemExit) as exc_info:
        if unified:
            ingestion_cli.main(["baal_indexer", *arguments])
        else:
            baal_indexer.main(arguments)

    assert exc_info.value.code == 2
    assert message in capsys.readouterr().err


def test_run_rejects_invalid_range_before_provider_or_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        baal_indexer,
        "Web3",
        lambda *_args, **_kwargs: pytest.fail("invalid range reached provider"),
    )
    monkeypatch.setattr(
        baal_indexer, "get_db", lambda: pytest.fail("invalid range opened database")
    )

    with pytest.raises(ValueError, match="--from-block must be non-negative"):
        baal_indexer.run(from_block=-1)


def test_to_block_zero_is_forwarded_as_explicit_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, int | None]] = []
    monkeypatch.setattr(baal_indexer, "run", lambda **kwargs: calls.append(kwargs))

    baal_indexer.main(["--from-block", "0", "--to-block", "0"])

    assert calls == [{"from_block": 0, "to_block": 0}]


def test_run_preserves_explicit_zero_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    ranges: list[tuple[int, int, int]] = []

    class _Web3:
        HTTPProvider = staticmethod(lambda _url: object())

        def __init__(self, _provider: object) -> None:
            self.eth = SimpleNamespace(block_number=99)

    class _Database:
        closed = False

        def close(self) -> None:
            self.closed = True

    database = _Database()
    monkeypatch.setattr(baal_indexer, "Web3", _Web3)
    monkeypatch.setattr(
        baal_indexer,
        "BaalReadClient",
        lambda **_kwargs: SimpleNamespace(_baal=object()),
    )
    monkeypatch.setattr(baal_indexer, "get_last_synced_block", lambda *_args: 5)
    monkeypatch.setattr(baal_indexer, "get_db", lambda: database)
    monkeypatch.setattr(baal_indexer, "_get_protocol_id", lambda _db: None)
    monkeypatch.setattr(
        baal_indexer,
        "batch_ranges",
        lambda start, end, size: ranges.append((start, end, size)) or [],
    )
    monkeypatch.setattr(baal_indexer, "update_indexer_status", lambda *_args: None)

    assert baal_indexer.run(from_block=0, to_block=0) == 0
    assert ranges == [(0, 0, baal_indexer.BLOCK_BATCH)]
    assert database.closed


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        baal_indexer.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["baal_indexer", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
