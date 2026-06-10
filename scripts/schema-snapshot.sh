#!/usr/bin/env bash
# ============================================================
# schema-snapshot.sh — Export Directus schema as JSON snapshot
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SNAPSHOT_DIR="$PROJECT_DIR/schemas/directus/snapshots"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$SNAPSHOT_DIR"

echo "=== Kokonut Intelligence Platform — Schema Snapshot ==="
echo ""

# Source environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

DIRECTUS_URL="${PUBLIC_URL:-http://localhost:8055}"

# Authenticate
echo "Authenticating with Directus..."
AUTH_RESPONSE=$(curl -s -X POST "$DIRECTUS_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")

TOKEN=$(echo "$AUTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to authenticate with Directus"
    echo "Response: $AUTH_RESPONSE"
    exit 1
fi

echo "Authenticated."

# Get schema snapshot
echo "Fetching schema snapshot..."
SNAPSHOT_FILE="$SNAPSHOT_DIR/schema_$TIMESTAMP.json"

curl -s -X GET "$DIRECTUS_URL/schema/snapshot" \
    -H "Authorization: Bearer $TOKEN" \
    -o "$SNAPSHOT_FILE"

if [ -s "$SNAPSHOT_FILE" ]; then
    echo "Snapshot saved: $SNAPSHOT_FILE"
    echo "Size: $(wc -c < "$SNAPSHOT_FILE") bytes"

    # Also save as latest
    cp "$SNAPSHOT_FILE" "$SNAPSHOT_DIR/schema_latest.json"
    echo "Also saved as: $SNAPSHOT_DIR/schema_latest.json"
else
    echo "ERROR: Snapshot file is empty"
    exit 1
fi

echo ""
echo "=== Snapshot Complete ==="
