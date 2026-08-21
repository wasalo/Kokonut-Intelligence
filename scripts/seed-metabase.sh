#!/usr/bin/env bash
# ============================================================
# seed-metabase.sh — Configure Metabase with database connection
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

echo "=== Kokonut Intelligence Platform — Metabase Setup ==="
echo ""

# Source secrets (SOPS encrypted .env.sops, or plaintext .env fallback)
source_secrets warn

# Wait for Metabase
echo "Waiting for Metabase to start (this may take a few minutes)..."
until curl -s http://localhost:3001/api/health | grep -q "ok" 2>/dev/null; do
    sleep 5
done
echo "Metabase is ready."

echo ""
echo "Metabase is running at http://localhost:3001"
echo ""
echo "Manual setup steps:"
echo "  1. Open http://localhost:3001 in your browser"
echo "  2. Create your admin account"
echo "  3. Add a database connection:"
echo "     - Database type: PostgreSQL"
echo "     - Display name: Kokonut Intelligence"
echo "     - Host: database"
echo "     - Port: 5432"
echo "     - Database name: kokonut_intelligence"
echo "     - Username: kokonut"
echo "     - Password: (from .env POSTGRES_PASSWORD)"
echo "  4. Save and explore the data"
echo ""
echo "Recommended dashboards to create:"
echo "  - Farm Operations Overview"
echo "  - Crop NOI Report"
echo "  - Expense Tracker"
echo "  - Harvest & Sales"
echo "  - Loss Rate Analysis"
echo "  - Location Baseline Comparison"
echo ""
