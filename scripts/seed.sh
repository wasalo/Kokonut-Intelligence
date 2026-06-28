#!/usr/bin/env bash
# ============================================================
# seed.sh — Load schema and seed data into the platform
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence Platform — Seed Data ==="
echo ""

# Source environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
else
    echo "ERROR: .env file not found. Run ./scripts/setup.sh first."
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

# Apply schema files
echo ""
echo "Applying schema files..."

SCHEMA_DIR="$PROJECT_DIR/schemas/postgres"
for schema_file in "$SCHEMA_DIR"/*.sql; do
    filename=$(basename "$schema_file")
    echo "  Applying: $filename"
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$schema_file"
done

echo ""
echo "Schema applied successfully."

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
if [ -f "$PERMISSIONS_FILE" ]; then
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence < "$PERMISSIONS_FILE"
    echo "Directus permissions applied."
else
    echo "No permissions file found at $PERMISSIONS_FILE — skipping."
fi

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

echo ""
echo "=== Seed Complete ==="
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Create your admin account (if not auto-created)"
echo "  3. Import Baserow data: python migrations/baserow_to_postgres/migrate.py --config config.json --dry-run"
echo "  4. Configure Metabase at http://localhost:3001"
echo ""
