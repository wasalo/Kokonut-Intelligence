"""
Revenue Multiplier Dimension Tests

Integration tests against the real database.
Requires a running PostgreSQL with seed data.

Usage:
    python3 -m tests.test_revenue_multiplier
    python3 -m pytest tests/test_revenue_multiplier.py -v
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_defaults():
    """Test that config module loads defaults without DB."""
    from services.revenue_multiplier.config import get_config, _DEFAULTS

    config = get_config(conn=None)
    assert config["replication_cost_usd"] == 15000
    assert config["loop_multiplier"] == 2.5
    assert config["carbon_credit_price_usd"] == 25.0
    assert config["biodiversity_credit_price_usd"] == 35.0
    assert config["impact_certificate_price_usd"] == 10.0
    assert config["shared_savings_per_ha_usd"] == 50
    assert config["new_partners_potential"] == 3
    assert config["loss_reduction_target_pct"] == 50
    assert config["buyer_uplift_pct"] == 30
    assert config["bioinput_savings_pct"] == 70
    assert config["bioinput_switching_benefit_pct"] == 50
    assert config["default_processing_uplift"] == 1.3
    assert isinstance(config["processing_uplift"], dict)
    assert "Maize" in config["processing_uplift"]


def test_config_invalidation():
    """Test that cache invalidation forces reload."""
    from services.revenue_multiplier.config import get_config, invalidate_cache

    invalidate_cache()
    config = get_config(conn=None)
    assert config["replication_cost_usd"] == 15000


def test_analyze_location_structure():
    """Test that analyze_location returns correct structure (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.analyzer import analyze_location

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    result = analyze_location(location_id)

    assert result.location_id == location_id
    assert len(result.dimensions) == 10
    assert result.total_opportunity_usd >= 0
    assert 0 <= result.overall_score <= 100
    assert result.generated_at is not None

    # Each dimension should have required fields
    for dim in result.dimensions:
        assert dim.dimension_id is not None
        assert dim.dimension_name is not None
        assert 0 <= dim.score <= 100
        assert dim.impact_usd >= 0
        assert dim.confidence in ("high", "medium", "low")


def test_crop_mix_dimension():
    """Test crop_mix analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import crop_mix

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = crop_mix.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "crop_mix_optimization"
    assert 0 <= dim.score <= 100
    assert dim.impact_usd >= 0
    assert dim.confidence in ("high", "medium", "low")


def test_loss_reduction_dimension():
    """Test loss_reduction analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import loss_reduction

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = loss_reduction.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "loss_rate_reduction"
    assert 0 <= dim.score <= 100


def test_buyer_channel_dimension():
    """Test buyer_channel analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import buyer_channel

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = buyer_channel.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "buyer_channel_selection"
    assert 0 <= dim.score <= 100


def test_value_added_dimension():
    """Test value_added analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import value_added

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = value_added.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "value_added_processing"
    assert 0 <= dim.score <= 100


def test_web3_replication_dimension():
    """Test web3_replication analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import web3_replication

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = web3_replication.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "web3_funded_replication"
    assert 0 <= dim.score <= 100


def test_bioinput_dimension():
    """Test bioinput analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import bioinput

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = bioinput.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "bioinput_production"
    assert 0 <= dim.score <= 100


def test_public_goods_dimension():
    """Test public_goods analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import public_goods

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = public_goods.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "public_goods_funding"
    assert 0 <= dim.score <= 100


def test_ecological_verification_dimension():
    """Test ecological_verification analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import ecological_verification

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = ecological_verification.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "ecological_verification"
    assert 0 <= dim.score <= 100


def test_partner_sponsorship_dimension():
    """Test partner_sponsorship analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import partner_sponsorship

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = partner_sponsorship.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "partner_sponsorship"
    assert 0 <= dim.score <= 100


def test_regional_clusters_dimension():
    """Test regional_clusters analysis (requires DB)."""
    from services.ingestion.base import get_db
    from services.revenue_multiplier.dimensions import regional_clusters

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    db.close()

    if not row:
        print("  SKIP: No locations in database")
        return

    location_id = str(row[0])
    conn = get_db()
    dim = regional_clusters.analyze(conn, location_id)
    conn.close()

    assert dim.dimension_id == "regional_farm_clusters"
    assert 0 <= dim.score <= 100


def test_forecast_output_queries_use_calculated_at():
    """Revenue multiplier dimensions must use forecast_output.calculated_at."""
    from pathlib import Path

    dimension_dir = Path(__file__).resolve().parents[1] / "services" / "revenue_multiplier" / "dimensions"
    offenders = []
    for path in dimension_dir.glob("*.py"):
        source = path.read_text()
        if "forecast_output" in source and "ORDER BY created_at" in source:
            offenders.append(path.name)
    assert not offenders, f"Use calculated_at for forecast_output ordering: {offenders}"


if __name__ == "__main__":
    print("=== Revenue Multiplier Tests ===")
    tests = [
        test_config_defaults,
        test_config_invalidation,
        test_analyze_location_structure,
        test_crop_mix_dimension,
        test_loss_reduction_dimension,
        test_buyer_channel_dimension,
        test_value_added_dimension,
        test_web3_replication_dimension,
        test_bioinput_dimension,
        test_public_goods_dimension,
        test_ecological_verification_dimension,
        test_partner_sponsorship_dimension,
        test_regional_clusters_dimension,
        test_forecast_output_queries_use_calculated_at,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n  Pass: {passed}/{passed + failed}")
    if failed:
        print(f"  Fail: {failed}")
        sys.exit(1)
    else:
        print("  All revenue multiplier tests passed ✓")
