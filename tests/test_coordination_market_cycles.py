"""Market-cycle classification tests."""

import pytest

from services.analytics.coordination import create_alliance, list_alliances
from services.ingestion.base import get_db


def test_slow_fast_and_standard_cycles_are_distinct():
    conn = get_db()
    alliances = [create_alliance(f"Cycle test {cycle}", "Cycle classification", market_cycle=cycle) for cycle in ("slow", "standard", "fast")]
    try:
        rows = {row["market_cycle"] for row in list_alliances() if row["id"] in {item["id"] for item in alliances}}
        assert rows == {"slow", "standard", "fast"}
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = ANY(%s::uuid[])", ([item["id"] for item in alliances],))
        conn.commit()


def test_alliance_types_preserve_legal_distinctions():
    schema = open("schemas/postgres/240_coordination_alliance_types.sql").read()
    for alliance_type in ("joint_venture", "equity_alliance", "nonequity_alliance"):
        assert alliance_type in schema
    assert "ownership" in schema.lower()
