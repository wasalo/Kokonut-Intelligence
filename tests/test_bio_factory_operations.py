"""Bio-organic fertilizer operations hub tests."""

from pathlib import Path

from services.agents.bio_factory_agent import synthesize_bio_factory
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_bio_factory_batch,
    generate_bio_input_provenance,
    generate_bio_quality_test,
    generate_bio_recipe_library,
    generate_bio_regional_input,
)


SCHEMA = Path("schemas/postgres/043_bio_factory_operations.sql")
SEED = Path("schemas/seeds/044_bio_factory_operations.sql")
PILOT_SEED = Path("schemas/seeds/043_pilot_bio_factory_operations.sql")
PILOT_RECIPES = Path("schemas/seeds/045_pilot_bio_factory_recipes.sql")
EAS_SEED = Path("schemas/seeds/014_pilot_celo_eas.sql")


def test_bio_factory_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "bio_factory_batch",
        "bio_input_provenance",
        "bio_recipe_library",
        "bio_factory_distribution",
        "bio_factory_quality_test",
        "bio_ingredient_composition_reference",
        "bio_regional_input_availability",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_bio_factory_batch_summary",
        "v_public_bio_input_provenance_summary",
        "v_public_bio_recipe_library_summary",
        "v_public_bio_factory_quality_test_summary",
        "v_public_bio_regional_input_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "quality_warnings TEXT[]" in text
    assert "microbial_strain" in text


def test_bio_factory_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "bio_batch_yield_pct",
        "bio_input_provenance_rate_pct",
        "bio_recipe_reuse_count",
        "bio_quality_test_pass_rate_pct",
        "bio_distribution_recipient_count",
        "bio_lac_input_share_pct",
    ]:
        assert metric in text
    for sql in [
        "57_bio_factory_batches.sql",
        "58_input_provenance.sql",
        "59_recipe_library.sql",
        "60_quality_distribution.sql",
        "61_regional_inputs.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "57_bio_factory_batches.json",
        "58_input_provenance.json",
        "59_recipe_library.json",
        "60_quality_distribution.json",
        "61_regional_inputs.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_composition_reference_seeded_with_pdf_data() -> None:
    text = SEED.read_text()
    ingredients = [
        "Bone meal", "Blood meal", "Feather meal",
        "Poultry manure (chicken)", "Cattle manure (cow)", "Swine manure (pig)",
        "Alfalfa meal", "Cottonseed meal", "Neem cake",
        "Kelp meal (Ascophyllum)", "Sargassum (Caribbean)",
        "Vermicompost (worm castings)", "Aerobic compost (mixed)",
        "Compost tea (aerated)", "Fish emulsion (fermented)",
        "Seaweed extract (kelp tea)", "Manure tea",
        "Green manure (legume cover crop)", "Humic acid (leonardite)",
        "Rhizobium inoculant", "Trichoderma harzianum", "Bacillus subtilis",
        "Mycorrhizal fungi (AMF)", "Azospirillum brasilense",
    ]
    for ingredient in ingredients:
        assert ingredient in text, f"Missing ingredient: {ingredient}"
    assert "n_pct_typical" in text
    assert "p_pct_typical" in text
    assert "k_pct_typical" in text
    assert "Sargassum" in text and "Caribbean" in text
    assert "arsenic" in text.lower()
    # Verify microbial inoculant entries exist with correct category
    assert "microbial_inoculant" in text
    assert "fixes_nitrogen" in text
    assert "solubilizes_phosphorus" in text
    assert "biocontrol" in text


def test_regional_input_availability_seeded_with_lac_data() -> None:
    text = SEED.read_text()
    for entry in [
        "Sargassum seaweed", "Cocoa pod husks", "Banana residues",
        "Coffee pulp", "Sugarcane bagasse", "Sesbania green manure",
        "Ascophyllum nodosum", "Coconut coir and husks",
    ]:
        assert entry in text, f"Missing regional entry: {entry}"
    for region in ["caribbean", "central_america", "south_america", "mexico", "latin_america_general"]:
        assert region in text
    assert "salts and arsenic" in text
    assert "Red Diamond Compost" in text


def test_pilot_seed_has_lac_aware_bio_factory_examples() -> None:
    text = PILOT_SEED.read_text()
    assert "Adelphi 2026 vermicompost batch A" in text
    assert "Adelphi 2026 compost tea batch B" in text
    assert "Adelphi 2026 bokashi batch C" in text
    assert "Banana stems (chopped)" in text
    assert "Coconut coir" in text
    assert "Chicken manure (aged)" in text
    assert "Sargassum seaweed (washed)" in text
    assert "Adelphi vermicompost recipe v1" in text
    assert "Tropical bokashi recipe" in text
    assert "Compost tea aerated brew" in text
    assert "Sargassum extract (Caribbean)" in text
    assert "Sabana Grande de Boya" in text
    assert "Dominican Republic" in text
    assert "Monte Plata" in text
    assert "smallholder_pilot_evidence" in text or "not a commercial guarantee" in text.lower()
    assert "salts and arsenic" in text.lower()

    # Additional recipes from 045_pilot_bio_factory_recipes.sql
    recipes_text = PILOT_RECIPES.read_text()
    assert "Fish emulsion (anaerobic fermented)" in recipes_text
    assert "Manure tea (steeped)" in recipes_text
    assert "Tropical aerobic compost" in recipes_text
    assert "Seaweed extract (kelp steep)" in recipes_text
    assert "Coffee pulp (composted)" in recipes_text
    assert "Fish waste (fresh scraps)" in recipes_text
    assert "adelphi-recipe-fish-emulsion-v1" in recipes_text
    assert "adelphi-recipe-manure-tea-v1" in recipes_text
    assert "adelphi-recipe-aerobic-compost-v1" in recipes_text
    assert "adelphi-recipe-seaweed-kelp-v1" in recipes_text
    # 4 original + 2 additional + 2 microbial = 8 recipes total
    assert PILOT_SEED.read_text().count("INSERT INTO bio_recipe_library") >= 4
    assert recipes_text.count("INSERT INTO bio_recipe_library") >= 6
    # 4 original + 2 additional = 6 input provenance rows total
    assert PILOT_SEED.read_text().count("INSERT INTO bio_input_provenance") >= 4
    assert recipes_text.count("INSERT INTO bio_input_provenance") >= 2
    # Microbial biofertilizer recipes
    assert "Rhizobium inoculant (carrier-based seed treatment)" in recipes_text
    assert "Trichoderma biofertilizer (rice bran carrier)" in recipes_text
    assert "adelphi-recipe-rhizobium-inoculant-v1" in recipes_text
    assert "adelphi-recipe-trichoderma-biofertilizer-v1" in recipes_text
    assert "microbial_biofertilizer" in recipes_text


def test_bio_factory_agent_task_catalogue_and_validation() -> None:
    assert "bio_factory_synthesis" in list_tasks()
    task = get_task("bio_factory_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("bio_factory_synthesis", {}) == ["Missing required output field: summary"]


def test_bio_factory_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "batch_name": "Adelphi vermicompost batch A",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "batch_type": "vermicompost",
                    "production_method": "vermicomposting",
                    "production_start_date": "2026-04-01",
                    "production_end_date": "2026-05-15",
                    "input_kg_total": 180,
                    "output_kg_total": 153,
                    "output_liters_total": None,
                    "batch_yield_pct": 85,
                    "moisture_pct": 65,
                    "temperature_c": 22.5,
                    "ph_level": 7.2,
                    "microbial_strain": None,
                    "public_summary": "Batch summary.",
                    "limitations": ["Yield varies."],
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "input_name": "Sargassum (washed)",
                    "input_category": "marine_material",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "batch_id": None,
                    "supplier_name": "Caribbean sargassum processor",
                    "supplier_verified": True,
                    "organic_certified": True,
                    "origin_country": "Caribbean region",
                    "origin_region": "Caribbean Sargassum Belt",
                    "input_kg": 25,
                    "nutrient_n_pct": 1.0,
                    "nutrient_p_pct": 0.3,
                    "nutrient_k_pct": 5.0,
                    "quality_warnings": ["untreated_sargassum_may_contain_salts_and_arsenic"],
                    "public_summary": "Sargassum ingredient summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "recipe_name": "Adelphi vermicompost recipe v1",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "recipe_type": "solid_fertilizer",
                    "recipe_category": "vermicompost",
                    "description": "Vermicompost recipe.",
                    "fermentation_days": 45,
                    "target_c_n_ratio": 30,
                    "target_moisture_pct": 65,
                    "target_temperature_c": 22.5,
                    "target_ph": 7.0,
                    "dilution_ratio": None,
                    "application_method": "Side-dress around plant base",
                    "quality_warnings": [],
                    "source_reference": "Kokonut Biofactory research",
                    "public_summary": "Vermicompost recipe summary.",
                    "limitations": ["Yield varies."],
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 4:
                return [{
                    "test_date": "2026-05-25",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "batch_id": None,
                    "test_type": "nutrient_analysis",
                    "parameter_name": "NPK total",
                    "measured_value": 4.2,
                    "unit": "pct",
                    "target_min": 3.0,
                    "target_max": 6.0,
                    "pass_fail": "pass",
                    "lab_name": "Adelphi on-site lab",
                    "lab_accredited": False,
                    "public_summary": "NPK pass.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "region_scope": "caribbean",
                "input_name": "Sargassum seaweed",
                "input_category": "marine_material",
                "country": "Caribbean region",
                "subregion": "Caribbean Sargassum Belt",
                "seasonality": "Year-round peaks",
                "cautions": ["untreated_sargassum_may_contain_salts_and_arsenic"],
                "quality_considerations": "Washed and processed sargassum.",
                "typical_suppliers": "Caribbean sargassum processors",
                "public_summary": "Caribbean sargassum regional summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_bio_factory(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["batch_count"] == 1
    assert summary["provenance_count"] == 1
    assert summary["recipe_count"] == 1
    assert summary["quality_test_count"] == 1
    assert summary["regional_input_count"] == 1
    assert summary["total_kg_produced"] == 153
    assert summary["lac_input_count"] >= 1
    assert summary["quality_pass_rate_pct"] == 100.0
    assert summary["ingredients_with_warnings"] == 1
    assert "smallholder pilot evidence" in summary["safety_note"].lower() or "advisory" in summary["safety_note"].lower()


def test_bio_factory_report_generators_registered() -> None:
    for report_type in [
        "bio_factory_batch",
        "bio_input_provenance",
        "bio_recipe_library",
        "bio_quality_test",
        "bio_regional_input",
    ]:
        assert report_type in REPORT_GENERATORS, f"Missing report type: {report_type}"


def test_bio_factory_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "batch_name": "Test batch",
                    "batch_type": "vermicompost",
                    "production_method": "vermicomposting",
                    "production_start_date": "2026-04-01",
                    "production_end_date": "2026-05-15",
                    "input_kg_total": 100,
                    "output_kg_total": 85,
                    "output_liters_total": None,
                    "batch_yield_pct": 85,
                    "public_summary": "Public summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "input_name": "Test input",
                    "input_category": "plant_residue",
                    "origin_region": "Monte Plata",
                    "supplier_verified": True,
                    "organic_certified": True,
                    "input_kg": 50,
                    "quality_warnings": [],
                    "public_summary": "Input summary.",
                    "evidence_maturity": 3,
                }]
            if self.calls == 3:
                return [{
                    "recipe_name": "Test recipe",
                    "recipe_type": "solid_fertilizer",
                    "recipe_category": "vermicompost",
                    "fermentation_days": 45,
                    "quality_warnings": [],
                    "public_summary": "Recipe summary.",
                    "evidence_maturity": 3,
                }]
            if self.calls == 4:
                return [{
                    "test_date": "2026-05-25",
                    "test_type": "nutrient_analysis",
                    "parameter_name": "NPK total",
                    "measured_value": 4.2,
                    "unit": "pct",
                    "pass_fail": "pass",
                    "lab_accredited": False,
                    "public_summary": "Test summary.",
                    "evidence_maturity": 3,
                }]
            return [{
                "region_scope": "caribbean",
                "input_name": "Test regional",
                "input_category": "marine_material",
                "cautions": [],
                "public_summary": "Regional summary.",
                "evidence_maturity": 3,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    location_id = "a0000000-0000-0000-0000-000000000001"
    batch = generate_bio_factory_batch(conn, location_id)
    provenance = generate_bio_input_provenance(conn, location_id)
    recipes = generate_bio_recipe_library(conn, location_id)
    quality = generate_bio_quality_test(conn, location_id)
    regional = generate_bio_regional_input(conn)

    assert batch["report_type"] == "bio_factory_batch"
    assert provenance["report_type"] == "bio_input_provenance"
    assert recipes["report_type"] == "bio_recipe_library"
    assert quality["report_type"] == "bio_quality_test"
    assert regional["report_type"] == "bio_regional_input"
    assert "smallholder pilot evidence" in batch["limitations"][0].lower()
    assert "advisory" in quality["limitations"][0].lower() or "certification" in quality["limitations"][0].lower()
    assert "salts and arsenic" in regional["limitations"][0].lower() or "sourcing notes" in regional["limitations"][0].lower()


def test_eas_bio_batch_placeholder_is_inactive() -> None:
    text = EAS_SEED.read_text()
    assert "Kokonut Bio-Batch" in text
    bio_batch_line = [
        line for line in text.splitlines()
        if "Kokonut Bio-Batch" in line
        and "0x9306a4cf6cc5a9c8aa6598a43bc62cfaa729f7490fe6b2e4cc0df10ec738ff29" in line
    ]
    assert len(bio_batch_line) == 1, (
        f"Expected exactly one Kokonut Bio-Batch EAS seed row with the Celo mainnet UID. "
        f"Found {len(bio_batch_line)} matching lines."
    )
    line = bio_batch_line[0]
    # Must use the real Celo mainnet UID, not the zero placeholder
    assert "0x0000000000000000000000000000000000000000000000000000000000000000" not in line, (
        f"Kokonut Bio-Batch EAS schema_uid must not be the 0x00 placeholder. Got: {line}"
    )
    # Must be active so attestations can be submitted
    assert line.rstrip(")").rstrip().endswith("TRUE"), (
        "Kokonut Bio-Batch EAS schema must be active (TRUE) after mainnet registration; "
        f"otherwise attestations cannot be submitted. Got: {line}"
    )


def test_regional_input_seed_evidence_maturity_and_idempotency() -> None:
    text = SEED.read_text()
    assert "INSERT INTO bio_regional_input_availability (" in text
    # Each VALUES tuple must end with `, 3, 'published')` so evidence_maturity=3 and status='published'.
    # v_public_bio_regional_input_summary filters on evidence_maturity >= 3, so without explicit
    # evidence_maturity every regional row would be invisible to dashboards, reports, and the agent.
    regional_block = text.split("INSERT INTO bio_regional_input_availability (", 1)[1]
    for line in regional_block.splitlines():
        if line.startswith("('") and "', 'published')" in line:
            assert ", 3, 'published')" in line, (
                "Each regional input VALUES tuple must set evidence_maturity=3 and status='published' "
                f"so the public view exposes it. Got: {line}"
            )
    # Idempotency: must use ON CONFLICT with a conflict target, not bare ON CONFLICT DO NOTHING.
    # Without a target, the bare clause has no effect (no natural key) and re-seeding duplicates rows.
    assert "ON CONFLICT (region_scope, input_name) DO UPDATE" in text, (
        "bio_regional_input_availability seed must use ON CONFLICT (region_scope, input_name) "
        "DO UPDATE so re-running seed.sh does not duplicate regional inputs."
    )
    assert "ON CONFLICT DO NOTHING" not in regional_block, (
        "Bare ON CONFLICT DO NOTHING without a target has no effect; replace with "
        "ON CONFLICT (region_scope, input_name) DO UPDATE SET ..."
    )


if __name__ == "__main__":
    test_bio_factory_schema_defines_records_and_public_views()
    test_bio_factory_seed_and_dashboards_exist()
    test_composition_reference_seeded_with_pdf_data()
    test_regional_input_availability_seeded_with_lac_data()
    test_pilot_seed_has_lac_aware_bio_factory_examples()
    test_bio_factory_agent_task_catalogue_and_validation()
    test_bio_factory_agent_summarizes_public_safe_records()
    test_bio_factory_report_generators_registered()
    test_bio_factory_report_generators_public_safe()
    test_eas_bio_batch_placeholder_is_inactive()
    test_regional_input_seed_evidence_maturity_and_idempotency()
