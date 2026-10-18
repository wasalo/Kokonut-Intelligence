"""Regression checks for the offline SDK/PostgreSQL schema guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_sdk_schema_parity", ROOT / "scripts" / "check-sdk-schema-parity.py"
)
assert SPEC is not None and SPEC.loader is not None
SCHEMA_GUARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCHEMA_GUARD
SPEC.loader.exec_module(SCHEMA_GUARD)


def test_column_type_inventory_reads_base_sql_declarations(tmp_path):
    schema = tmp_path / "fixture.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    count INTEGER NOT NULL,
    ratio NUMERIC(12, 4),
    tags TEXT[],
    location GEOMETRY(Point, 4326)
);
""",
        encoding="utf-8",
    )

    assert SCHEMA_GUARD.table_column_types(schema, "sdk_guard_fixture") == {
        "id": "UUID",
        "count": "INTEGER",
        "ratio": "NUMERIC(12, 4)",
        "tags": "TEXT[]",
        "location": "GEOMETRY(POINT, 4326)",
    }


def test_column_type_inventory_applies_additions_and_type_migrations(tmp_path, monkeypatch):
    schema = tmp_path / "base.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    label TEXT
);
""",
        encoding="utf-8",
    )
    migrations = tmp_path / "schemas" / "postgres"
    migrations.mkdir(parents=True)
    (migrations / "001_fixture.sql").write_text(
        """ALTER TABLE sdk_guard_fixture ADD COLUMN score NUMERIC(12, 4);
ALTER TABLE sdk_guard_fixture ALTER COLUMN score TYPE NUMERIC(14, 4);
ALTER TABLE public.sdk_guard_fixture ADD COLUMN source_alert_event_id UUID NOT NULL;
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(SCHEMA_GUARD, "ROOT", tmp_path)

    assert SCHEMA_GUARD.table_column_types(schema, "sdk_guard_fixture") == {
        "id": "UUID",
        "label": "TEXT",
        "score": "NUMERIC(14, 4)",
        "source_alert_event_id": "UUID",
    }
    assert "source_alert_event_id" not in SCHEMA_GUARD.table_nullable_columns(
        schema, "sdk_guard_fixture"
    )


def test_idempotent_add_column_does_not_override_existing_column_contract(tmp_path, monkeypatch):
    schema = tmp_path / "base.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    required_label TEXT NOT NULL
);
""",
        encoding="utf-8",
    )
    migrations = tmp_path / "schemas" / "postgres"
    migrations.mkdir(parents=True)
    (migrations / "001_fixture.sql").write_text(
        "ALTER TABLE sdk_guard_fixture ADD COLUMN IF NOT EXISTS id TEXT;\n"
        "ALTER TABLE sdk_guard_fixture ADD COLUMN IF NOT EXISTS required_label TEXT;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(SCHEMA_GUARD, "ROOT", tmp_path)

    assert SCHEMA_GUARD.table_nullable_columns(schema, "sdk_guard_fixture") == set()
    assert SCHEMA_GUARD.table_column_types(schema, "sdk_guard_fixture") == {
        "id": "UUID",
        "required_label": "TEXT",
    }


def test_sql_check_literal_inventory_reads_base_constraints_and_migrations(tmp_path, monkeypatch):
    schema = tmp_path / "base.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    kind TEXT CHECK (kind IN ('one', 'two'))
);
""",
        encoding="utf-8",
    )
    migrations = tmp_path / "schemas" / "postgres"
    migrations.mkdir(parents=True)
    (migrations / "001_fixture.sql").write_text(
        "ALTER TABLE sdk_guard_fixture ADD CONSTRAINT state_check CHECK (state IN ('ready', 'held'));\n"
        "ALTER TABLE sdk_guard_fixture ADD CONSTRAINT nullable_check "
        "CHECK (kind IS NULL OR kind IN ('one', 'two'));\n"
        "ALTER TABLE sdk_guard_fixture ADD CONSTRAINT conditional_check "
        "CHECK (created_by IS NULL OR state IN ('draft', 'submitted'));\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(SCHEMA_GUARD, "ROOT", tmp_path)

    assert SCHEMA_GUARD.table_check_literals(schema, "sdk_guard_fixture") == {
        "kind": ("one", "two"),
        "state": ("ready", "held"),
    }


def test_sdk_literal_contracts_match_exact_sql_check_values():
    expected = {
        ("SensorAnomalyEffect", "outcome"): ("no_match", "cooldown", "alert_created"),
        ("ActuationLog", "actuator_type"): (
            "irrigation", "pest_control", "fertilization", "notification", "custom"
        ),
        ("ActuationLog", "status"): (
            "pending", "requires_approval", "approved", "sent", "acknowledged",
            "executed", "failed", "cancelled"
        ),
        ("Organization", "org_type"): (
            "cooperative", "nonprofit", "dao", "enterprise", "collective", "other"
        ),
        ("Organization", "status"): ("active", "inactive", "dissolved"),
        ("OrganizationMember", "membership_type"): (
            "owned", "affiliated", "sponsored", "partner"
        ),
        ("OrganizationMember", "role"): ("primary", "satellite", "partner", "incubated"),
        ("OrganizationMember", "status"): ("active", "inactive", "suspended"),
        ("AlertRule", "actuator_type"): (
            "irrigation", "pest_control", "fertilization", "notification", "custom"
        ),
        ("SensorAlert", "actuation_status"): (
            "pending", "sent", "acknowledged", "executed", "failed", "requires_approval"
        ),
        ("AttestationRecord", "verdict"): (
            "pending", "approved", "rejected", "needs_info"
        ),
        ("TimeSeriesForecast", "model_type"): (
            "arima", "exponential_smoothing", "prophet", "naive", "seasonal_naive"
        ),
        ("TimeSeriesForecast", "status"): ("active", "superseded", "expired"),
        ("DemandForecast", "forecast_type"): (
            "time_series", "buyer_pipeline", "seasonal_decomposition", "hybrid"
        ),
        ("DemandForecast", "status"): ("draft", "submitted", "verified", "published"),
        ("MarketSizeEstimate", "market_scope"): (
            "local", "regional", "national", "international"
        ),
        ("MarketSizeEstimate", "status"): ("draft", "submitted", "verified", "published"),
        ("DemandTrend", "analysis_type"): (
            "seasonal_pattern", "price_elasticity", "moving_average", "trend_decomposition"
        ),
        ("DemandTrend", "status"): ("draft", "submitted", "verified", "published"),
        ("BuyerDemandSignal", "buyer_type"): (
            "processor", "direct", "market", "restaurant", "retailer", "export", "cooperative", "other"
        ),
        ("BuyerDemandSignal", "signal_type"): (
            "verbal_intent", "written_order", "purchase_order", "forecast_request", "recurring_order"
        ),
        ("BuyerDemandSignal", "commitment_level"): (
            "firm", "probable", "possible", "exploratory"
        ),
        ("BuyerDemandSignal", "status"): (
            "draft", "submitted", "verified", "published", "rejected"
        ),
        ("ProductionMarketMatch", "status"): (
            "draft", "submitted", "verified", "published"
        ),
        ("BuyerSegment", "segment_type"): (
            "value_based", "behavior_based", "need_based", "tier_based"
        ),
        ("BuyerSegment", "segment_value"): (
            "high_value", "medium_value", "low_value", "potential", "at_risk", "churned"
        ),
        ("BuyerSegment", "status"): ("draft", "submitted", "verified", "published"),
        ("TrendEstimate", "direction"): (
            "improving", "stable", "declining", "insufficient_data"
        ),
        ("TrendEstimate", "confidence_level"): (
            "high", "moderate", "low", "insufficient_data"
        ),
        ("TrendSmoothing", "smoothing_type"): (
            "moving_average", "weighted_moving_average", "exponential", "holt_linear"
        ),
        ("ChangePoint", "detection_method"): (
            "cusum", "pelt", "binary_segmentation", "window_slider"
        ),
        ("ChangePoint", "direction"): ("increase", "decrease", "variance_change"),
        ("ChangePoint", "status"): ("detected", "confirmed", "dismissed"),
        ("SeasonalDecomposition", "decomposition_method"): ("classical", "stl", "x11"),
        ("PriceObservation", "aggregation_method"): (
            "single", "median_consensus", "weighted_average", "on_chain_attested"
        ),
        ("SoilSample", "status"): ("draft", "submitted", "verified", "published", "rejected"),
        ("SoilCarbonMeasurement", "status"): (
            "draft", "submitted", "verified", "published", "rejected"
        ),
        ("SpeciesObservation", "status"): (
            "draft", "submitted", "verified", "published", "rejected"
        ),
        ("SpeciesObservation", "trophic_level"): (
            "producer", "primary_consumer", "secondary_consumer", "decomposer", "omnivore"
        ),
        ("SpeciesObservation", "conservation_status"): (
            "critically_endangered", "endangered", "vulnerable", "near_threatened",
            "least_concern", "data_deficient", "not_evaluated"
        ),
        ("FarmTask", "category"): (
            "planting", "weeding", "irrigation", "spraying", "harvesting",
            "maintenance", "training", "reporting", "other"
        ),
        ("FarmTask", "priority"): ("low", "medium", "high", "critical"),
        ("FarmTask", "status"): ("pending", "in_progress", "completed", "cancelled"),
    }
    python_aliases = SCHEMA_GUARD.python_literal_aliases(
        ROOT / "sdk" / "python" / "kokonut" / "types.py"
    )
    typescript_aliases = SCHEMA_GUARD.typescript_literal_aliases(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    python_types = SCHEMA_GUARD.python_model_field_types(
        ROOT / "sdk" / "python" / "kokonut" / "types.py"
    )
    typescript_types = SCHEMA_GUARD.typescript_model_field_types(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    discovered = set()
    for model, (schema_file, table) in SCHEMA_GUARD.MODEL_TABLES.items():
        sql_types = SCHEMA_GUARD.table_column_types(
            ROOT / "schemas" / "postgres" / schema_file, table
        )
        discovered.update(
            (model, column)
            for column in SCHEMA_GUARD.table_check_literals(
                ROOT / "schemas" / "postgres" / schema_file, table
            )
            if SCHEMA_GUARD.sql_type_family(sql_types.get(column, "")) == "string"
        )
    assert discovered == set(expected)

    for (model, column), expected_values in expected.items():
        schema_file, table = SCHEMA_GUARD.MODEL_TABLES[model]
        sql_values = SCHEMA_GUARD.table_check_literals(
            ROOT / "schemas" / "postgres" / schema_file, table
        )[column]
        assert sql_values == expected_values
        assert SCHEMA_GUARD.python_type_matches_literals(
            python_types[model][column], python_aliases, sql_values
        )
        assert SCHEMA_GUARD.typescript_type_matches_literals(
            typescript_types[model][column], typescript_aliases, sql_values
        )
    assert not SCHEMA_GUARD.python_type_matches_literals(
        "OrganizationStatus", python_aliases, expected[("Organization", "org_type")]
    )


def test_sql_type_families_cover_scalars_and_postgis_shapes():
    assert SCHEMA_GUARD.sql_type_family("UUID") == "string"
    assert SCHEMA_GUARD.sql_type_family("NUMERIC(12, 4)") == "number"
    assert SCHEMA_GUARD.sql_type_family("INTEGER") == "integer"
    assert SCHEMA_GUARD.sql_type_family("TEXT[]") == "string_array"
    assert SCHEMA_GUARD.sql_type_family("UUID[]") == "string_array"
    assert SCHEMA_GUARD.sql_type_family("JSONB") == "jsonb"
    assert SCHEMA_GUARD.sql_type_family("GEOMETRY(POINT, 4326)") == "geojson_point"
    assert SCHEMA_GUARD.sql_type_family("GEOMETRY(POLYGON, 4326)") == "geojson_polygon"


def test_typescript_literal_alias_parser_accepts_multiline_unions(tmp_path):
    typescript = tmp_path / "types.ts"
    typescript.write_text(
        "export type Fixture =\n"
        "  | 'first'\n"
        "  | 'second';\n"
        "export type Next = 'third';\n",
        encoding="utf-8",
    )

    assert SCHEMA_GUARD.typescript_literal_aliases(typescript) == {
        "Fixture": ("first", "second"),
        "Next": ("third",),
    }


def test_sdk_scalar_types_match_sql_families_and_nullable_unions():
    assert SCHEMA_GUARD.python_type_matches_family("Optional[float]", "number")
    assert SCHEMA_GUARD.python_type_matches_family("Optional[List[str]]", "string_array")
    assert not SCHEMA_GUARD.python_type_matches_family("Optional[str]", "number")

    assert SCHEMA_GUARD.typescript_type_matches_family("number | null", "integer")
    assert SCHEMA_GUARD.typescript_type_matches_family("'draft' | 'published' | null", "string")
    assert SCHEMA_GUARD.typescript_type_matches_family("string[]", "string_array")
    assert not SCHEMA_GUARD.typescript_type_matches_family("string", "number")
    assert SCHEMA_GUARD.python_type_matches_family("Optional[GeoJSONPoint]", "geojson_point")
    assert SCHEMA_GUARD.python_type_matches_family("Optional[GeoJSONPolygon]", "geojson_polygon")
    assert SCHEMA_GUARD.typescript_type_matches_family("GeoJSONPoint | null", "geojson_point")
    assert SCHEMA_GUARD.typescript_type_matches_family(
        "GeoJSONPolygon | null", "geojson_polygon"
    )
    assert SCHEMA_GUARD.python_type_matches_family("Optional[JSONObject]", "json_object")
    assert SCHEMA_GUARD.python_type_matches_family(
        "Optional[List[JSONObject]]", "json_object_array"
    )
    assert SCHEMA_GUARD.typescript_type_matches_family("JSONObject | null", "json_object")
    assert SCHEMA_GUARD.typescript_type_matches_family(
        "JSONObject[] | null", "json_object_array"
    )
    assert not SCHEMA_GUARD.python_type_matches_family(
        "Optional[Dict[str, Any]]", "json_object"
    )
    assert not SCHEMA_GUARD.typescript_type_matches_family(
        "Record<string, unknown> | null", "json_object"
    )


def test_sdk_spatial_field_shapes_match_canonical_postgis_types():
    python_types = SCHEMA_GUARD.python_model_field_types(
        ROOT / "sdk" / "python" / "kokonut" / "types.py"
    )
    typescript_types = SCHEMA_GUARD.typescript_model_field_types(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    checked = 0
    for model, (schema_file, table) in SCHEMA_GUARD.MODEL_TABLES.items():
        for column, sql_type in SCHEMA_GUARD.table_column_types(
            ROOT / "schemas" / "postgres" / schema_file, table
        ).items():
            family = SCHEMA_GUARD.sql_type_family(sql_type)
            if family not in {"geojson_point", "geojson_polygon"}:
                continue
            checked += 1
            assert SCHEMA_GUARD.python_type_matches_family(
                python_types[model][column], family
            ), f"Python {model}.{column} does not match {sql_type}"
            assert SCHEMA_GUARD.typescript_type_matches_family(
                typescript_types[model][column], family
            ), f"TypeScript {model}.{column} does not match {sql_type}"
    assert checked == 10


def test_sdk_jsonb_fields_match_declared_object_or_object_array_contracts():
    python_types = SCHEMA_GUARD.python_model_field_types(
        ROOT / "sdk" / "python" / "kokonut" / "types.py"
    )
    typescript_types = SCHEMA_GUARD.typescript_model_field_types(
        ROOT / "sdk" / "javascript" / "src" / "types.ts"
    )
    checked = 0
    for model, (schema_file, table) in SCHEMA_GUARD.MODEL_TABLES.items():
        for column, sql_type in SCHEMA_GUARD.table_column_types(
            ROOT / "schemas" / "postgres" / schema_file, table
        ).items():
            if SCHEMA_GUARD.sql_type_family(sql_type) != "jsonb":
                continue
            family = SCHEMA_GUARD.JSONB_MODEL_SHAPES[(model, column)]
            checked += 1
            assert SCHEMA_GUARD.python_type_matches_family(
                python_types[model][column], family
            ), f"Python {model}.{column} does not match {family}"
            assert SCHEMA_GUARD.typescript_type_matches_family(
                typescript_types[model][column], family
            ), f"TypeScript {model}.{column} does not match {family}"
    assert checked == 79
    assert SCHEMA_GUARD.JSONB_MODEL_SHAPES[("ReportSnapshot", "negative_findings")] == (
        "json_object_array"
    )


def test_sql_enum_inventory_reads_type_definitions_and_column_cast_constraints(tmp_path, monkeypatch):
    schema_dir = tmp_path / "schemas" / "postgres"
    schema_dir.mkdir(parents=True)
    base = schema_dir / "001_fixture.sql"
    base.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_enum_fixture (
    id UUID PRIMARY KEY,
    status TEXT
);
""",
        encoding="utf-8",
    )
    (schema_dir / "015_fixture_constraints.sql").write_text(
        """DO $$ BEGIN
    CREATE TYPE fixture_status AS ENUM ('draft', 'published');
END $$;
ALTER TABLE sdk_enum_fixture ADD CONSTRAINT fixture_status_check
    CHECK (status::fixture_status IS NOT NULL);
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(SCHEMA_GUARD, "ROOT", tmp_path)

    enum_types = SCHEMA_GUARD.postgres_enum_types()

    assert enum_types["fixture_status"] == ("draft", "published")
    assert SCHEMA_GUARD.table_enum_columns(base, "sdk_enum_fixture", enum_types) == {
        "status": "fixture_status"
    }


def test_sdk_enum_annotations_match_all_mapped_postgres_enum_constraints():
    python_path = ROOT / "sdk" / "python" / "kokonut" / "types.py"
    typescript_path = ROOT / "sdk" / "javascript" / "src" / "types.ts"
    python_types = SCHEMA_GUARD.python_model_field_types(python_path)
    typescript_types = SCHEMA_GUARD.typescript_model_field_types(typescript_path)
    python_enums = SCHEMA_GUARD.python_literal_aliases(python_path)
    typescript_enums = SCHEMA_GUARD.typescript_literal_aliases(typescript_path)
    sql_enums = SCHEMA_GUARD.postgres_enum_types()
    checked = 0

    for model, (schema_file, table) in SCHEMA_GUARD.MODEL_TABLES.items():
        enum_columns = SCHEMA_GUARD.table_enum_columns(
            ROOT / "schemas" / "postgres" / schema_file,
            table,
            sql_enums,
        )
        for column, enum_type in enum_columns.items():
            values = sql_enums[enum_type]
            checked += 1
            assert SCHEMA_GUARD.python_type_matches_enum(
                python_types[model][column], python_enums, values
            ), f"Python {model}.{column} does not match SQL enum {enum_type}"
            assert SCHEMA_GUARD.typescript_type_matches_enum(
                typescript_types[model][column], typescript_enums, values
            ), f"TypeScript {model}.{column} does not match SQL enum {enum_type}"

    assert checked == 23
