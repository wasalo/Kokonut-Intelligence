"""Impact Network tests: schema, seeds across all 5 components."""

from pathlib import Path

SCHEMA_064 = Path("schemas/postgres/064_organization.sql")
SCHEMA_065 = Path("schemas/postgres/065_funding_flow.sql")
SCHEMA_066 = Path("schemas/postgres/066_ecosystem_landscape.sql")
SCHEMA_067 = Path("schemas/postgres/067_impact_bounties.sql")
SCHEMA_068 = Path("schemas/postgres/068_impact_office.sql")
SEED = Path("schemas/seeds/064-068_impact_network.sql")


# ---------------------------------------------------------------------------
# Schema tests — Organization
# ---------------------------------------------------------------------------

def test_schema_064_defines_tables() -> None:
    text = SCHEMA_064.read_text()
    for table in ["organization", "organization_member", "organization_wallet"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_064_defines_view() -> None:
    text = SCHEMA_064.read_text()
    assert "CREATE OR REPLACE VIEW v_public_organization_summary" in text


def test_schema_064_adds_fk_to_location() -> None:
    text = SCHEMA_064.read_text()
    assert "ALTER TABLE location ADD COLUMN IF NOT EXISTS organization_id" in text


# ---------------------------------------------------------------------------
# Schema tests — Funding Flow
# ---------------------------------------------------------------------------

def test_schema_065_defines_tables() -> None:
    text = SCHEMA_065.read_text()
    for table in ["donor", "funding_campaign", "donation", "impact_payout_rule", "impact_payout_execution"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_065_defines_views() -> None:
    text = SCHEMA_065.read_text()
    for view in ["v_public_funding_campaigns", "v_public_donation_summary", "v_public_impact_payout_summary"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


# ---------------------------------------------------------------------------
# Schema tests — Ecosystem Landscape
# ---------------------------------------------------------------------------

def test_schema_066_defines_views() -> None:
    text = SCHEMA_066.read_text()
    for view in ["v_ecosystem_farm_network", "v_ecosystem_farm_detail", "v_farm_funding_page"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


# ---------------------------------------------------------------------------
# Schema tests — Impact Bounties
# ---------------------------------------------------------------------------

def test_schema_067_defines_tables() -> None:
    text = SCHEMA_067.read_text()
    for table in ["impact_bounty", "impact_bounty_submission"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


# ---------------------------------------------------------------------------
# Schema tests — Impact Office
# ---------------------------------------------------------------------------

def test_schema_068_defines_tables() -> None:
    text = SCHEMA_068.read_text()
    for table in ["impact_office_run", "impact_office_step", "impact_office_alert"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_organization() -> None:
    text = SEED.read_text()
    assert "kokonut-adelphi" in text
    assert "Kokonut Adelphi" in text
    assert "cooperative" in text


def test_seed_has_funding() -> None:
    text = SEED.read_text()
    assert "donor" in text
    assert "funding_campaign" in text
    assert "donation" in text
    assert "impact_payout_rule" in text
    assert "Adelphi Syntropic Expansion" in text
    assert "45000.00" in text


def test_seed_has_bounties() -> None:
    text = SEED.read_text()
    assert "impact_bounty" in text
    assert "Soil Sampling Campaign" in text
    assert "Biodiversity Survey" in text
    assert "50.00" in text
    assert "100.00" in text


def test_seed_has_office() -> None:
    text = SEED.read_text()
    assert "impact_office_run" in text
    assert "impact_office_step" in text
    assert "impact_office_alert" in text
    assert "full_cycle" in text
    assert "campaign_goal_reached" in text


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------

def test_orchestrator_import() -> None:
    from services.office import run_full_cycle, run_bounty_cycle, run_funding_cycle, run_landscape_refresh
    assert callable(run_full_cycle)
    assert callable(run_bounty_cycle)
    assert callable(run_funding_cycle)
    assert callable(run_landscape_refresh)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_064_defines_tables()
    test_schema_064_defines_view()
    test_schema_064_adds_fk_to_location()
    test_schema_065_defines_tables()
    test_schema_065_defines_views()
    test_schema_066_defines_views()
    test_schema_067_defines_tables()
    test_schema_068_defines_tables()
    test_seed_has_organization()
    test_seed_has_funding()
    test_seed_has_bounties()
    test_seed_has_office()
    test_orchestrator_import()
    print("All tests passed.")
