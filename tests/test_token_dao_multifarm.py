"""Token, DAO, and multi-farm integration tests."""

from pathlib import Path

SCHEMAS = {
    "token": Path("schemas/postgres/096_token_integration.sql"),
    "voting": Path("schemas/postgres/097_hybrid_voting.sql"),
    "multifarm": Path("schemas/postgres/098_multi_farm.sql"),
}


def test_token_schema_exists():
    assert SCHEMAS["token"].exists()


def test_token_has_core_tables():
    content = SCHEMAS["token"].read_text()
    for table in ["governance_token", "tree_token_binding", "staking_position",
                   "yield_distribution", "token_balance_snapshot"]:
        assert table in content


def test_token_supports_external_and_internal():
    content = SCHEMAS["token"].read_text()
    assert "contract_source_code" in content
    assert "abi" in content
    assert "deployment_mode" in content
    assert "external" in content
    assert "internal" in content


def test_token_has_1_1_binding():
    content = SCHEMAS["token"].read_text()
    assert "tree_token_binding" in content
    assert "tree_record_id" in content
    assert "token_id_onchain" in content
    assert "wallet_address" in content


def test_token_has_staking():
    content = SCHEMAS["token"].read_text()
    assert "staking_position" in content
    assert "lock_period_days" in content
    assert "accumulated_rewards" in content


def test_token_has_yield():
    content = SCHEMAS["token"].read_text()
    assert "yield_distribution" in content
    assert "distribution_per_token" in content
    assert "total_staked_tokens" in content


def test_token_service_exists():
    assert Path("services/analytics/token_integration.py").exists()


def test_token_has_bind_tree():
    from services.analytics.token_integration import bind_tree
    assert callable(bind_tree)


def test_token_has_staking():
    from services.analytics.token_integration import create_staking_position
    assert callable(create_staking_position)


def test_token_has_yield():
    from services.analytics.token_integration import compute_yield
    assert callable(compute_yield)


def test_token_has_voting_power():
    from services.analytics.token_integration import get_voting_power
    assert callable(get_voting_power)


# --- Hybrid Voting ---


def test_voting_schema_exists():
    assert SCHEMAS["voting"].exists()


def test_voting_has_core_tables():
    content = SCHEMAS["voting"].read_text()
    for table in ["dao_vote", "dao_proposal_extended", "reputation_token", "delegation_record"]:
        assert table in content


def test_voting_has_qv():
    content = SCHEMAS["voting"].read_text()
    assert "sqrt_weight" in content
    assert "quadratic" in content


def test_voting_has_reputation():
    content = SCHEMAS["voting"].read_text()
    assert "reputation_token" in content
    assert "non-transferable" in content or "earned_from" in content


def test_voting_has_delegation():
    content = SCHEMAS["voting"].read_text()
    assert "delegation_record" in content
    assert "delegator_id" in content
    assert "delegate_id" in content


def test_voting_service_exists():
    assert Path("services/analytics/hybrid_voting.py").exists()


def test_voting_has_cast_vote():
    from services.analytics.hybrid_voting import cast_quadratic_vote
    assert callable(cast_quadratic_vote)


def test_voting_has_compute_result():
    from services.analytics.hybrid_voting import compute_proposal_result
    assert callable(compute_proposal_result)


def test_voting_has_delegate():
    from services.analytics.hybrid_voting import delegate_vote
    assert callable(delegate_vote)


def test_voting_has_earn_reputation():
    from services.analytics.hybrid_voting import earn_reputation
    assert callable(earn_reputation)


# --- Multi-Farm ---


def test_multifarm_schema_exists():
    assert SCHEMAS["multifarm"].exists()


def test_multifarm_has_core_tables():
    content = SCHEMAS["multifarm"].read_text()
    for table in ["farm_onboarding_workflow", "cross_farm_portfolio", "farm_template_instance"]:
        assert table in content


def test_multifarm_has_workflow_steps():
    content = SCHEMAS["multifarm"].read_text()
    assert "land_assessment" in content
    assert "community_engagement" in content
    assert "go_live" in content


def test_multifarm_service_exists():
    assert Path("services/analytics/multi_farm.py").exists()


def test_multifarm_has_instantiate():
    from services.analytics.multi_farm import instantiate_farm_from_template
    assert callable(instantiate_farm_from_template)


def test_multifarm_has_portfolio():
    from services.analytics.multi_farm import compute_cross_farm_portfolio
    assert callable(compute_cross_farm_portfolio)


def test_multifarm_has_comparison():
    from services.analytics.multi_farm import get_farm_comparison
    assert callable(get_farm_comparison)


def test_multifarm_seed_has_genesis():
    seed = Path("schemas/seeds/098_multi_farm.sql").read_text()
    assert "Kokonut Genesis" in seed
    assert "Barahona" in seed
