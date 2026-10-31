"""Location UUID preflight for the hand-written marketplace CLI."""

from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.analytics import cli_marketplace


@pytest.mark.parametrize(
    "argv",
    [
        ["create-listing", "--location-id", "bad", "--crop", "yuca", "--quantity", "1"],
        ["market-overview", "--location-id", "bad"],
        ["create-alert", "--location-id", "bad", "--crop", "yuca", "--threshold", "1"],
        ["list-active", "--location-id", "bad"],
    ],
)
def test_location_scoped_commands_reject_bad_uuid_before_database(monkeypatch, argv):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_marketplace.main(argv)

    assert error.value.code == 2
    get_db.assert_not_called()


def test_list_active_keeps_unscoped_mode_when_location_filter_is_omitted(
    monkeypatch, capsys
):
    db = Mock()
    get_db = Mock(return_value=db)
    list_active = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "list_active_listings", list_active)

    cli_marketplace.main(["list-active", "--json"])

    get_db.assert_called_once_with()
    list_active.assert_called_once_with(db, None, None, 50, 0)
    db.close.assert_called_once_with()
    assert capsys.readouterr().out.strip() == '{\n  "total": 0,\n  "listings": []\n}'


def test_list_active_accepts_valid_location_filter(monkeypatch):
    location_id = str(uuid4())
    db = Mock()
    get_db = Mock(return_value=db)
    list_active = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "list_active_listings", list_active)

    cli_marketplace.main(["list-active", "--location-id", location_id, "--json"])

    list_active.assert_called_once_with(db, location_id, None, 50, 0)
    db.close.assert_called_once_with()


@pytest.mark.parametrize(
    "option,value",
    [
        ("--limit", "0"),
        ("--limit", "-1"),
        ("--limit", "101"),
        ("--limit", "1000000"),
        ("--limit", "not-an-int"),
        ("--offset", "-1"),
        ("--offset", "10001"),
        ("--offset", "not-an-int"),
    ],
)
def test_list_active_rejects_bad_pagination_before_database(monkeypatch, option, value):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_marketplace.main(["list-active", option, value])

    assert error.value.code == 2
    get_db.assert_not_called()


@pytest.mark.parametrize("limit,offset", [(1, 0), (100, 10_000)])
def test_list_active_forwards_valid_pagination_boundaries(monkeypatch, limit, offset):
    db = Mock()
    get_db = Mock(return_value=db)
    list_active = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "list_active_listings", list_active)

    cli_marketplace.main(
        ["list-active", "--limit", str(limit), "--offset", str(offset), "--json"]
    )

    list_active.assert_called_once_with(db, None, None, limit, offset)
    db.close.assert_called_once_with()


@pytest.mark.parametrize(
    "limit,offset",
    [(0, 0), (101, 0), (50, -1), (50, 10_001), ("50", 0), (50, True)],
)
def test_list_active_service_rejects_invalid_pagination_before_cursor(
    limit, offset
):
    db = Mock()

    with pytest.raises(ValueError, match="limit|offset"):
        cli_marketplace.list_active_listings(db, limit=limit, offset=offset)

    db.cursor.assert_not_called()


@pytest.mark.parametrize(
    "argv, operation",
    [
        (
            ["create-listing", "--location-id", "A0000000-0000-4000-8000-000000000001",
             "--crop", "yuca", "--quantity", "1", "--json"],
            "create_listing",
        ),
        (
            ["market-overview", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
            "get_market_overview",
        ),
        (
            ["create-alert", "--location-id", "A0000000-0000-4000-8000-000000000001",
             "--crop", "yuca", "--threshold", "1", "--json"],
            "create_price_alert",
        ),
        (
            ["list-active", "--location-id", "A0000000-0000-4000-8000-000000000001", "--json"],
            "list_active_listings",
        ),
    ],
)
def test_location_arguments_are_canonical_before_database_handler(
    monkeypatch, argv, operation
):
    canonical_location = "a0000000-0000-4000-8000-000000000001"
    db = Mock()
    get_db = Mock(return_value=db)
    handler = Mock(return_value={"total": 0, "listings": []})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, operation, handler)

    cli_marketplace.main(argv)

    assert handler.call_args.args[1] == canonical_location
    db.close.assert_called_once_with()


def test_create_buyer_keeps_descriptive_location_value(monkeypatch):
    db = Mock()
    get_db = Mock(return_value=db)
    create_buyer = Mock(return_value={})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "create_buyer_profile", create_buyer)

    cli_marketplace.main(
        ["create-buyer", "--name", "Test buyer", "--location", "Santo Domingo", "--json"]
    )

    create_buyer.assert_called_once()
    assert create_buyer.call_args.args[3] == "Santo Domingo"
    assert create_buyer.call_args.kwargs["preferences"] == {}
    assert create_buyer.call_args.kwargs["contact_info"] == {}
    db.close.assert_called_once_with()


def test_create_listing_rejects_invalid_harvest_date_before_database(
    monkeypatch, capsys
):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_marketplace.main(
            [
                "create-listing", "--location-id", str(uuid4()), "--crop", "yuca",
                "--quantity", "1", "--harvest-date", "2026-02-30",
            ]
        )

    assert error.value.code == 2
    assert "--harvest-date must be a valid ISO date" in capsys.readouterr().err
    get_db.assert_not_called()


def test_create_listing_forwards_parsed_harvest_date(monkeypatch):
    location_id = str(uuid4())
    db = Mock()
    get_db = Mock(return_value=db)
    create_listing = Mock(return_value={"created": True})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "create_listing", create_listing)

    cli_marketplace.main(
        [
            "create-listing", "--location-id", location_id, "--crop", "yuca",
            "--quantity", "1", "--harvest-date", "2026-02-28", "--json",
        ]
    )

    assert create_listing.call_args.kwargs["harvest_date"] == date(2026, 2, 28)
    db.close.assert_called_once_with()


@pytest.mark.parametrize(
    "option,value",
    [
        ("--preferences", "not-json"),
        ("--contact-info", "{broken"),
        ("--preferences", "[]"),
        ("--contact-info", '"email@example.test"'),
    ],
)
def test_create_buyer_rejects_invalid_or_non_object_json_before_database(
    monkeypatch, capsys, option, value
):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_marketplace.main(
            ["create-buyer", "--name", "Test buyer", option, value]
        )

    assert error.value.code == 2
    assert "must be a valid JSON object" in capsys.readouterr().err
    get_db.assert_not_called()


def test_create_buyer_forwards_decoded_json_values(monkeypatch):
    db = Mock()
    get_db = Mock(return_value=db)
    create_buyer = Mock(return_value={"created": True})
    monkeypatch.setattr("services.ingestion.base.get_db", get_db)
    monkeypatch.setattr(cli_marketplace, "create_buyer_profile", create_buyer)

    cli_marketplace.main(
        [
            "create-buyer", "--name", "Test buyer",
            "--preferences", '{"crops":["yuca"],"volume":2}',
            "--contact-info", '{"email":"buyer@example.test"}', "--json",
        ]
    )

    assert create_buyer.call_args.kwargs["preferences"] == {
        "crops": ["yuca"],
        "volume": 2,
    }
    assert create_buyer.call_args.kwargs["contact_info"] == {
        "email": "buyer@example.test"
    }
    db.close.assert_called_once_with()
