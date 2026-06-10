#!/usr/bin/env bash
# ============================================================
# setup.sh — First-run bootstrap for Kokonut Intelligence Platform
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kokonut Intelligence Platform — Setup ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker is not installed"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: docker compose is not available"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "IMPORTANT: Edit .env with your secrets before starting services"
    echo ""
fi

# Create data directories
echo "Creating data directories..."
mkdir -p "$PROJECT_DIR/data/postgres"
mkdir -p "$PROJECT_DIR/data/uploads"
mkdir -p "$PROJECT_DIR/data/metabase"
mkdir -p "$PROJECT_DIR/data/clickhouse"

# Start services
echo "Starting infrastructure..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "Service health:"
docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your secrets"
echo "  2. Access Directus at http://localhost:8055"
echo "  3. Access Metabase at http://localhost:3000"
echo "  4. Run: ./scripts/seed.sh (to load pilot data)"
echo ""
