"""Tests that the Land Stewardship Trust enforcement logic holds (KI-9).

Verifies the schema-level guards the methodology (docs/land-stewardship-trust.md)
depends on actually exist and behave: governed lifecycle + farm_registry gate on
the public views. Uses the repo's `db` fixture (real connection, skips if none).
"""

import pytest


@pytest.mark.parametrize("table", [
    "land_stewardship_commitment",
    "regenerative_outcome_summary",
    "adaptive_stewardship_review",
    "community_governance_mechanism",
    "capital_alignment_assessment",
])
def test_governed_lifecycle_column_exists(db, table):
    cur = db.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'status'",
        (table,),
    )
    assert cur.fetchone() is not None, f"{table} missing status column"


def test_public_views_gate_on_farm_registry(db):
    """v_public_* views must reference farm_registry_record verification."""
    cur = db.cursor()
    for view in (
        "v_public_land_stewardship_summary",
        "v_public_regenerative_outcome_summary",
        "v_public_adaptive_stewardship_summary",
    ):
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", (view,))
        defn = cur.fetchone()
        if defn is None:
            pytest.skip(f"{view} not present in this DB (expected in CI/staging)")
        assert "farm_registry_record" in defn[0], f"{view} missing farm_registry gate"
        assert "status IN ('verified', 'published')" in defn[0], \
            f"{view} gate does not require verified farm_registry_record"


def test_land_stewardship_model_includes_commons_trust(db):
    """The commons_trust_pathway model the methodology requires must be valid."""
    cur = db.cursor()
    cur.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'chk_land_stewardship_model'"
    )
    chk = cur.fetchone()
    assert chk is not None, "chk_land_stewardship_model constraint missing"
    assert "commons_trust_pathway" in chk[0], \
        "commons_trust_pathway not an allowed stewardship_model"
