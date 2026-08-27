"""Tests for MiCA asset classification guardrail (KI-11)."""

import pytest

from services.compliance.mica import (
    ASSETS,
    MicaConcern,
    assert_perimeter,
    classify,
)


def test_known_assets_inventoried():
    # every instrument named in the KI-11 assessment is classified
    for a in ("kokonut_credit_token", "guild_points", "credit_basket",
              "credit_marketplace", "vKKN_governance", "cusd_denom",
              "farm_mrv", "attestation"):
        assert a in ASSETS


def test_cusd_is_prohibited_as_own_emt():
    c = classify("cusd_denom")
    assert c.concern is MicaConcern.PROHIBITED
    assert not c.eu_offerable
    assert "use_authorised_emt_provider" in c.required_controls
    assert "never_issue_as_own" in c.required_controls


def test_farm_mrv_outside_perimeter():
    c = classify("farm_mrv")
    assert c.concern is MicaConcern.OUTSIDE
    assert c.eu_offerable
    assert not c.blocks_without_human()


def test_credit_basket_blocks_without_controls():
    c = classify("credit_basket")
    assert c.concern is MicaConcern.HIGH
    assert c.blocks_without_human()


def test_assert_perimeter_blocks_prohibited():
    with pytest.raises(PermissionError):
        assert_perimeter("cusd_denom")


def test_assert_perimeter_allows_outside():
    # must not raise
    assert_perimeter("farm_mrv")
    assert_perimeter("attestation")
