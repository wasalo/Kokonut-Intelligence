#!/usr/bin/env bash
# ============================================================
# seed-pilot.sh — Load pilot farm data
# ============================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence — Pilot Farm Data ==="
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

DB_CONTAINER="kokonut-intelligence-database-1"

# Wait for database
echo "Waiting for PostgreSQL..."
until docker exec "$DB_CONTAINER" pg_isready -U kokonut -d kokonut_intelligence > /dev/null 2>&1; do
    sleep 2
done
echo "PostgreSQL is ready."

# Apply pilot seed files (only 001-005)
echo ""
echo "Applying pilot farm seed data..."

SEED_DIR="$PROJECT_DIR/schemas/seeds"
for seed_file in "$SEED_DIR"/00[1-5]_pilot_*.sql; do
    filename=$(basename "$seed_file")
    echo "  Applying: $filename"
    docker exec -i "$DB_CONTAINER" psql -U kokonut -d kokonut_intelligence < "$seed_file" 2>&1 | grep -v "^SET$\|^$\|^INSERT 0" || true
done

echo ""
echo "=== Pilot Farm Data Loaded ==="
echo ""
echo "Location: Kokonut Demo Farm — Kisumu"
echo "Farm: Main Farm (12 ha)"
echo "Plots: Plot A (maize), Plot B (cassava), Plot C (mixed)"
echo "Crops: Maize, Cassava, Beans, Sweet Potato"
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
echo "  - 5 sensor devices + 15 readings"
echo "  - 15 wallet activity events"
echo "  - 5 digital lego interactions"
echo "  - 2 attestation schemas + 4 records"
echo "  - 3 forecast scenarios (Baseline, Optimistic, Conservative)"
echo "  - 24 forecast outputs"
echo "  - 3 NOI snapshots"
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Browse pilot data in the admin UI"
echo "  3. Run forecast engine: python3 -m services.forecast.engine"
echo ""
