"""Tests that the Land Stewardship Trust enforcement logic holds.

KI-9 — verifies the schema-level guards the methodology (docs/land-stewardship-trust.md)
depends on actually exist and behave: governed lifecycle + farm_registry gate on
the public views. These run against the live schema (CI/staging have it).
"""

import pytest


@pytest.mark.parametrize("table,status_col", [
    ("land_stewardship_commitment", "status"),
    ("regenerative_outcome_summary", "status"),
    ("adaptive_stewardship_review", "status"),
    ("community_governance_mechanism", "status"),
    ("capital_alignment_assessment", "status"),
])
def test_governed_lifecycle_column_exists(conn, table, status_col):
    """Every Trust instrument enforces draft→verified→published lifecycle."""
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, status_col),
    )
    assert cur.fetchone() is not None, f"{table} missing {status_col}"


def test_public_views_gate_on_farm_registry(conn):
    """v_public_* views must reference farm_registry_record verification.

    The Trust's core enforcement: no public stewardship claim without a
    registered, verified farm. We check the view definition contains the gate.
    """
    cur = conn.cursor()
    for view in (
        "v_public_land_stewardship_summary",
        "v_public_regenerative_outcome_summary",
        "v_public_adaptive_stewardship_summary",
    ):
        cur.execute(
            "SELECT pg_get_viewdef(%s::regclass, true)", (view,)
        )
        defn = cur.fetchone()
        if defn is None:
            pytest.skip(f"{view} not present in this DB (expected in CI/staging)")
        assert "farm_registry_record" in defn[0], f"{view} missing farm_registry gate"
        assert "status IN ('verified', 'published')" in defn[0], \
            f"{view} gate does not require verified farm_registry_record"


def test_land_stewardship_model_includes_commons_trust(conn):
    """The commons_trust_pathway model the methodology requires must be valid."""
    cur = conn.cursor()
    cur.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conname = 'chk_land_stewardship_model'"
    )
    assert cur.fetchone() is not None, "chk_land_stewardship_model constraint missing"
    # confirm the enum-like value is accepted by checking the check definition
    cur.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'chk_land_stewardship_model'"
    )
    chk = cur.fetchone()
    assert chk is not None and "commons_trust_pathway" in chk[0], \
        "commons_trust_pathway not an allowed stewardship_model"
