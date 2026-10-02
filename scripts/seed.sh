#!/usr/bin/env bash
# ============================================================
# seed.sh — Load schema and seed data into the platform
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

REFERENCE_ONLY=false
if [ "${1:-}" = "--reference-only" ]; then
    REFERENCE_ONLY=true
elif [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 [--reference-only]"
    exit 0
elif [ "$#" -gt 0 ]; then
    echo "Unknown argument: $1" >&2
    exit 2
fi

echo "=== Kokonut Intelligence Platform — Seed Data ==="
echo ""

source_secrets strict

CH_SERVICE="${CH_SERVICE:-clickhouse}"
DB_WAIT_ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"

# Wait for database
echo "Waiting for PostgreSQL..."
wait_for_postgres
echo "PostgreSQL is ready."

if [ "$REFERENCE_ONLY" = "false" ]; then
    # Apply init.sql and extensions.sql (bind mounts removed from docker-compose.yml
    # to fix DinD failures where the source paths resolve to executor host directories).
    echo ""
    echo "Applying init.sql..."
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/config/postgres/init.sql"
    echo "Applying extensions.sql..."
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/config/postgres/extensions.sql"

    # Apply PostgreSQL schema and numbered seed migrations through the checksum-
    # tracked runner. Keep this as the only default PostgreSQL application path.
    echo ""
    echo "Applying PostgreSQL schema migrations..."
    python3 -m services.migration migrate --schemas-only
    echo "PostgreSQL schema migrations applied successfully."

    # Apply ClickHouse schemas
    echo ""
    echo "Applying ClickHouse schemas..."
    CH_SCHEMA_DIR="$PROJECT_DIR/schemas/clickhouse"
    if docker compose -f "$COMPOSE_FILE" exec -T "$CH_SERVICE" clickhouse-client --user kokonut --password "$CLICKHOUSE_PASSWORD" --query "SELECT 1" > /dev/null 2>&1; then
        for ch_file in "$CH_SCHEMA_DIR"/*.sql; do
            filename=$(basename "$ch_file")
            echo "  Applying: $filename"
            docker compose -f "$COMPOSE_FILE" exec -T "$CH_SERVICE" clickhouse-client --user kokonut --password "$CLICKHOUSE_PASSWORD" --multiquery < "$ch_file"
        done
        echo "ClickHouse schemas applied."
    else
        echo "ClickHouse not running — skipping."
    fi

    # Apply Directus permissions
    echo ""
    echo "Applying Directus permissions..."
    PERMISSIONS_FILE="$PROJECT_DIR/config/directus/permissions.sql"
    if [ -f "$PERMISSIONS_FILE" ] && docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=0 -U kokonut -d kokonut_intelligence -c "SELECT 1 FROM directus_roles LIMIT 1" >/dev/null 2>&1; then
        docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PERMISSIONS_FILE"
        echo "Directus permissions applied."
    else
        echo "Directus not running or no permissions file — skipping."
    fi
fi

# Curated pilot/reference seeds remain separate from schema migrations until
# every historical seed has passed clean-bootstrap and dependency validation.
if [ "${KOKONUT_RUN_CURATED_SEEDS:-true}" = "true" ]; then
CURATED_SEEDS=(
    "schemas/seeds/000_expense_categories.sql"
    "schemas/seeds/000_metric_definitions.sql"
    "schemas/seeds/022_metric_governance.sql"
    "schemas/seeds/103_flow_metrics.sql"
    "schemas/seeds/015_revenue_multiplier_config.sql"
    "schemas/seeds/023_impact_frameworks.sql"
    "schemas/seeds/027_carbon_framework_seeds.sql"
    "schemas/seeds/032_ebf_rubric.sql"
    "schemas/seeds/033_ebf_dashboard_datasets.sql"
    "schemas/seeds/034_ebf_p2_dashboard_datasets.sql"
    "schemas/seeds/035_holistic_wellbeing.sql"
    "schemas/seeds/036_financial_resilience_and_scaling.sql"
    "schemas/seeds/037_capital_efficiency_and_utility.sql"
    "schemas/seeds/038_commons_liberation_and_stewardship.sql"
    "schemas/seeds/039_gnh_alignment_and_inclusion.sql"
    "schemas/seeds/040_regenerative_outcomes_and_stewardship.sql"
    "schemas/seeds/041_open_source_capitalist_scaling.sql"
    "schemas/seeds/042_kokonut_commons_governance.sql"
    "schemas/seeds/044_bio_factory_operations.sql"
    "schemas/seeds/090_pitch_templates.sql"
    "schemas/seeds/091_business_architecture.sql"
    "schemas/seeds/092_technology_roadmap.sql"
    "schemas/seeds/105_stakeholder_vocabulary.sql"
    "schemas/seeds/106_stakeholder_engagement.sql"
    "schemas/seeds/107_stakeholder_cockpit.sql"
    "schemas/seeds/108_coordination_example.sql"
    "schemas/seeds/109_adelphi_governance_roles.sql"
    "schemas/seeds/110_adelphi_governance_circles.sql"
    "schemas/seeds/114_state_of_kokonut_funding.sql"
    "schemas/seeds/115_strategic_reserve.sql"
)

for seed_file in "${CURATED_SEEDS[@]}"; do
    echo ""
    echo "Seeding ${seed_file##*/}..."
    psql_exec "$PROJECT_DIR/$seed_file"
    echo "${seed_file##*/} seeded."
done
fi

echo ""
echo "=== Seed Complete ==="
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Create your admin account (if not auto-created)"
echo "  3. Optional BI: start Metabase with --profile metabase, then configure it at http://localhost:3001"
echo ""
