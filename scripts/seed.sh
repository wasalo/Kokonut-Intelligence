#!/usr/bin/env bash
# ============================================================
# seed.sh — Load schema and seed data into the platform
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

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

# Source secrets (SOPS encrypted .env.sops, or plaintext .env fallback)
if [ -f "$PROJECT_DIR/.env.sops" ]; then
    source "$SCRIPT_DIR/load-secrets.sh"
elif [ -f "$PROJECT_DIR/.env" ]; then
    if [ "${KOKONUT_ALLOW_PLAINTEXT_ENV:-}" = "true" ]; then
        set -a
        source "$PROJECT_DIR/.env"
        set +a
    else
        echo "ERROR: No .env.sops found. Set KOKONUT_ALLOW_PLAINTEXT_ENV=true to use plaintext .env." >&2
        exit 1
    fi
else
    echo "ERROR: No secrets found. Expected .env.sops or .env."
    exit 1
fi

COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
DB_SERVICE="${DB_SERVICE:-database}"
CH_SERVICE="${CH_SERVICE:-clickhouse}"
DB_WAIT_ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"

wait_for_postgres() {
    local attempt=1
    until docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" pg_isready -U kokonut -d kokonut_intelligence > /dev/null 2>&1; do
        if [ "$attempt" -ge "$DB_WAIT_ATTEMPTS" ]; then
            echo "ERROR: PostgreSQL service '$DB_SERVICE' is not ready after $((DB_WAIT_ATTEMPTS * 2)) seconds."
            return 1
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
}

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

# Seed expense categories
echo ""
echo "Seeding expense categories..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/000_expense_categories.sql"
echo "Expense categories seeded."

# Seed metric definitions
echo ""
echo "Seeding metric definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/000_metric_definitions.sql"
echo "Metric definitions seeded."

# Seed metric governance fields
echo ""
echo "Seeding metric governance fields..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/022_metric_governance.sql"
echo "Metric governance fields seeded."

# Seed VSM flow metrics (governed lead-time / FTY / rework definitions)
echo ""
echo "Seeding VSM flow metric definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/103_flow_metrics.sql"
echo "VSM flow metric definitions seeded."

# Seed revenue multiplier config
echo ""
echo "Seeding revenue multiplier config..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/015_revenue_multiplier_config.sql"
echo "Revenue multiplier config seeded."

# Seed Kokonut Framework reference data
echo ""
echo "Seeding Kokonut Framework reference data..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/023_impact_frameworks.sql"
echo "Kokonut Framework reference data seeded."

# Seed Carbon Framework reference data
echo ""
echo "Seeding Carbon Framework reference data (emission factors, benchmarks, protocols)..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/027_carbon_framework_seeds.sql"
echo "Carbon Framework reference data seeded."

# Seed EBF rubric reference data
echo ""
echo "Seeding EBF rubric reference data..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/032_ebf_rubric.sql"
echo "EBF rubric reference data seeded."

# Seed EBF dashboard dataset definitions
echo ""
echo "Seeding EBF dashboard dataset definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/033_ebf_dashboard_datasets.sql"
echo "EBF dashboard dataset definitions seeded."

# Seed EBF P2 portfolio dashboard dataset definitions
echo ""
echo "Seeding EBF portfolio dashboard dataset definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/034_ebf_p2_dashboard_datasets.sql"
echo "EBF portfolio dashboard dataset definitions seeded."

# Seed Holistic Well-being reference data
echo ""
echo "Seeding Holistic Well-being metric and dashboard definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/035_holistic_wellbeing.sql"
echo "Holistic Well-being definitions seeded."

# Seed Financial Resilience and Scaling reference data
echo ""
echo "Seeding Financial Resilience and Scaling definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/036_financial_resilience_and_scaling.sql"
echo "Financial Resilience and Scaling definitions seeded."

# Seed Capital Efficiency and Utility reference data
echo ""
echo "Seeding Capital Efficiency and Utility definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/037_capital_efficiency_and_utility.sql"
echo "Capital Efficiency and Utility definitions seeded."

# Seed Commons Liberation and Stewardship reference data
echo ""
echo "Seeding Commons Liberation and Stewardship definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/038_commons_liberation_and_stewardship.sql"
echo "Commons Liberation and Stewardship definitions seeded."

# Seed GNH Alignment and Inclusion reference data
echo ""
echo "Seeding GNH Alignment and Inclusion definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/039_gnh_alignment_and_inclusion.sql"
echo "GNH Alignment and Inclusion definitions seeded."

# Seed Regenerative Outcomes and Stewardship reference data
echo ""
echo "Seeding Regenerative Outcomes and Stewardship definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/040_regenerative_outcomes_and_stewardship.sql"
echo "Regenerative Outcomes and Stewardship definitions seeded."

# Seed Open Source Capitalist scaling economics reference data
echo ""
echo "Seeding Open Source Capitalist scaling definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/041_open_source_capitalist_scaling.sql"
echo "Open Source Capitalist scaling definitions seeded."

# Seed Kokonut Commons governance reference data
echo ""
echo "Seeding Kokonut Commons governance definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/042_kokonut_commons_governance.sql"
echo "Kokonut Commons governance definitions seeded."

# Seed Bio Factory Operations reference data
echo ""
echo "Seeding Bio Factory Operations definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/044_bio_factory_operations.sql"
echo "Bio Factory Operations definitions seeded."

# Seed the organization used by organization-grain reports
echo ""
echo "Seeding canonical pilot organization..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/113_pilot_organization.sql"
echo "Canonical pilot organization seeded."

# Seed audience-specific pitch templates
echo ""
echo "Seeding pitch templates..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/090_pitch_templates.sql"
echo "Pitch templates seeded."

# Seed Business Architecture reference data
echo ""
echo "Seeding Business Architecture capability and value-stream definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/091_business_architecture.sql"
echo "Business Architecture definitions seeded."

# Seed Technology and Capability Roadmap reference data
echo ""
echo "Seeding Technology and Capability Roadmap definitions..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/092_technology_roadmap.sql"
echo "Technology and Capability Roadmap definitions seeded."

# Seed canonical stakeholder vocabulary and pilot proxy interests
echo ""
echo "Seeding Stakeholder Ecosystem foundation..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/105_stakeholder_vocabulary.sql"
echo "Stakeholder Ecosystem foundation seeded."

# Seed stakeholder engagement foundation
echo ""
echo "Seeding Stakeholder Engagement foundation..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/106_stakeholder_engagement.sql"

echo "Seeding stakeholder cockpit datasets..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/107_stakeholder_cockpit.sql"
echo "Stakeholder Engagement foundation seeded."

# Seed a draft-only Adelphi coordination example. It contains no approval,
# activation, publication, benefit distribution, or private alliance evidence.
echo "Seeding draft Adelphi coordination example..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/108_coordination_example.sql"
echo "Draft Adelphi coordination example seeded."

# Seed the Adelphi role-and-circle governance pilot.
echo "Seeding Adelphi role-and-circle governance pilot..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/109_adelphi_governance_roles.sql"
echo "Adelphi role-and-circle governance pilot seeded."

echo "Seeding adjacent Adelphi governance circles..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/110_adelphi_governance_circles.sql"
echo "Adjacent Adelphi governance circles seeded."

# Seed State of Kokonut funding + ecosystem-actor participation (2021-2024 pilot).
echo "Seeding State of Kokonut funding data..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/114_state_of_kokonut_funding.sql"
echo "State of Kokonut funding data seeded."

echo "Seeding Strategic Reserve data..."
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PROJECT_DIR/schemas/seeds/115_strategic_reserve.sql"
echo "Strategic Reserve data seeded."

fi

echo ""
echo "=== Seed Complete ==="
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Create your admin account (if not auto-created)"
echo "  3. Configure Metabase at http://localhost:3001"
echo ""
