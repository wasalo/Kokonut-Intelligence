#!/usr/bin/env bash
# ============================================================
# seed-pilot.sh — Load pilot farm data
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

echo "=== Kokonut Intelligence — Pilot Farm Data ==="
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




# Wait for database
echo "Waiting for PostgreSQL..."
wait_for_postgres
echo "PostgreSQL is ready."

# Fail before applying any pilot records if tenant ownership/grant foundations
# have not been migrated. Pilot ownership evidence is seeded after locations.
if ! docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    psql -v ON_ERROR_STOP=1 -U kokonut -d kokonut_intelligence -Atqc \
    "SELECT EXISTS (
         SELECT 1
           FROM schema_migration
          WHERE migration_id = 'schema:388_tenant_aware_operator_grants.sql'
            AND status = 'applied'
     )" \
    | grep -qx t; then
    echo "ERROR: Apply ordered migrations through 388 before loading pilot data." >&2
    exit 1
fi

# Apply all pilot seed files
echo ""
echo "Applying pilot farm seed data..."

SEED_DIR="$PROJECT_DIR/schemas/seeds"

# Support seeds required before pilot files with foreign-key dependencies.
for seed_file in \
    "$SEED_DIR/001_pilot_farm.sql" \
    "$SEED_DIR/076_crisp_risk_scoring.sql" \
    "$SEED_DIR/024_adelphi_alignment.sql" \
    "$SEED_DIR/018_module_e_water_access.sql"; do
    if [ -f "$seed_file" ]; then
        filename=$(basename "$seed_file")
        echo "  Applying: $filename"
        seed_apply "$seed_file" pilot
    fi
done

for seed_file in "$SEED_DIR"/*_pilot_*.sql; do
    filename=$(basename "$seed_file")
    echo "  Applying: $filename"
    seed_apply "$seed_file" pilot
done

# MVP support seeds whose filenames are not *_pilot_*.sql.
for seed_file in \
    "$SEED_DIR/017_dashboard_datasets.sql" \
    "$SEED_DIR/020_gnosis_chain.sql" \
    "$SEED_DIR/021_metric_versions.sql" \
    "$SEED_DIR/022_metric_governance.sql" \
    "$SEED_DIR/023_impact_frameworks.sql" \
    "$SEED_DIR/027_carbon_framework_seeds.sql"; do
    if [ -f "$seed_file" ]; then
        filename=$(basename "$seed_file")
        echo "  Applying: $filename"
        seed_apply "$seed_file" pilot
    fi
done

# Pilot/reference files whose names do not use the *_pilot_*.sql convention.
for seed_file in \
    "$SEED_DIR/057_tree_tracking.sql" \
    "$SEED_DIR/099_coconut_syntropic_template.sql" \
    "$SEED_DIR/098_multi_farm.sql"; do
    if [ -f "$seed_file" ]; then
        filename=$(basename "$seed_file")
        echo "  Applying: $filename"
        seed_apply "$seed_file" pilot
    fi
done

# Ownership must be applied last: earlier pilot seeds create Adelphi's legacy
# organization assignment, and Genesis is created by 098_multi_farm.sql. The
# operating-tenant map skips future owner-confirmed locations until imported.
echo "  Applying: 120_kokonut_network_ownership.sql"
seed_apply "$SEED_DIR/120_kokonut_network_ownership.sql" pilot

echo "  Applying: 121_kokonut_network_tenant_owner_verification.sql"
seed_apply "$SEED_DIR/121_kokonut_network_tenant_owner_verification.sql" pilot

echo "  Applying: 122_kokonut_network_operating_tenant_map.sql"
seed_apply "$SEED_DIR/122_kokonut_network_operating_tenant_map.sql" pilot

echo ""
echo "=== Pilot Farm Data Loaded ==="
echo ""
echo "Location: Kokonut Adelphi — Sabana Grande de Boya"
echo "Farm: Kokonut Adelphi (1.5725 ha / 15,725 m2)"
echo "Plots: Syntropic Beds, Agroforestry Corridor, Nursery & Biofactory"
echo "Crops: Lettuce, Passion Fruit, Coconut, Eggs, Indian Yam"
echo "Period: Oct 2025 — Mar 2026"
echo ""
echo "Data includes:"
echo "  - 30 farm activities"
echo "  - 12 harvest events"
echo "  - 12 sales events (\$35,682 total revenue)"
echo "  - 40 expense events (\$4,485 total expenses)"
echo "  - 6 loss events"
echo "  - 24 labor events"
echo "  - 12 field notes"
echo "  - 6 soil samples"
echo "  - 12 weather observations"
echo "  - 6 remote sensing observations"
echo "  - plant, water, disease, and irrigation analytics records"
echo "  - 5 sensor devices + 15 readings"
echo "  - 15 wallet activity events"
echo "  - 5 digital lego interactions"
echo "  - 12 dapp sessions"
echo "  - 2 attestation schemas + 4 records"
echo "  - 3 forecast scenarios (Baseline, Optimistic, Conservative)"
echo "  - forecast outputs and NOI snapshots"
echo "  - dashboard datasets and metric version records"
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Browse pilot data in the admin UI"
echo "  3. Run forecast engine: python3 -m services.forecast.engine"
echo ""
