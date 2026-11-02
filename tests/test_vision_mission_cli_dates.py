"""Fail-fast date validation for the Vision/Mission CLI."""

from __future__ import annotations

import sys

import pytest

from services.analytics import cli_vision_mission


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--effective-date", "not-a-date"),
        ("--effective-date", "2026-02-30"),
        ("--effective-date", "20261030"),
        ("--review-date", "not-a-date"),
        ("--review-date", "2026-02-30"),
        ("--review-date", "20261030"),
    ],
)
def test_create_rejects_invalid_dates_before_service_call(monkeypatch, capsys, option, value):
    calls = []
    monkeypatch.setattr(cli_vision_mission, "create_statement", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["vision-mission", "create", "A statement", "--type", "vision", option, value])

    with pytest.raises(SystemExit) as exc:
        cli_vision_mission.main()

    assert exc.value.code == 2
    assert calls == []
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_create_forwards_canonical_dates_unchanged(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_vision_mission, "create_statement", lambda *args, **kwargs: calls.append((args, kwargs)) or {"id": "synthetic"})
    monkeypatch.setattr(cli_vision_mission, "_out", lambda _data: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vision-mission",
            "create",
            "A statement",
            "--type",
            "vision",
            "--effective-date",
            "2026-10-30",
            "--review-date",
            "2027-01-15",
        ],
    )

    cli_vision_mission.main()

    assert calls == [
        (
            ("A statement",),
            {
                "statement_type": "vision",
                "entity_type": "platform",
                "entity_id": None,
                "effective_date": "2026-10-30",
                "review_date": "2027-01-15",
            },
        )
    ]


def test_create_forwards_omitted_dates_as_none(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_vision_mission, "create_statement", lambda *args, **kwargs: calls.append((args, kwargs)) or {"id": "synthetic"})
    monkeypatch.setattr(cli_vision_mission, "_out", lambda _data: None)
    monkeypatch.setattr(sys, "argv", ["vision-mission", "create", "A statement", "--type", "mission"])

    cli_vision_mission.main()

    assert calls[0][1]["effective_date"] is None
    assert calls[0][1]["review_date"] is None

