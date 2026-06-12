#!/usr/bin/env bash
# ============================================================
# sandbox-setup.sh — Bootstrap the Kokonut developer sandbox
#
# Generates API keys, imports dashboards, seeds sample data,
# and prints connection info.
# ============================================================
set -euo pipefail

DIRECTUS_URL="${DIRECTUS_URL:-http://localhost:8055}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@kokonut.network}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-KokonutDev2026!}"

echo "============================================"
echo "  Kokonut Intelligence — Sandbox Setup"
echo "============================================"
echo ""

# ---------------------------------------------------------------
# 1. Wait for Directus to be healthy
# ---------------------------------------------------------------
echo "[1/5] Waiting for Directus at $DIRECTUS_URL ..."
for i in $(seq 1 60); do
    if curl -sf "$DIRECTUS_URL/server/health" > /dev/null 2>&1; then
        echo "      Directus is healthy."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "      ERROR: Directus did not become healthy in time."
        exit 1
    fi
    sleep 2
done

# ---------------------------------------------------------------
# 2. Authenticate and generate a sandbox static token
# ---------------------------------------------------------------
echo "[2/5] Authenticating as admin..."

LOGIN_RESP=$(curl -sf -X POST "$DIRECTUS_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

ADMIN_TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null || true)

if [ -z "$ADMIN_TOKEN" ]; then
    echo "      ERROR: Could not authenticate with Directus."
    echo "      Response: $LOGIN_RESP"
    exit 1
fi
echo "      Authenticated."

# Check if sandbox-role already exists, create if not
echo "      Creating sandbox role (if needed)..."
ROLE_RESP=$(curl -sf -X POST "$DIRECTUS_URL/roles" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"sandbox","description":"Sandbox API role with read/write access to operational data","admin_access":false,"app_access":true}' 2>/dev/null || true)

ROLE_ID=$(echo "$ROLE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['id'])" 2>/dev/null || true)

if [ -z "$ROLE_ID" ]; then
    # Role may already exist — fetch it
    ROLE_ID=$(curl -sf "$DIRECTUS_URL/roles?filter[name][eq]=sandbox" \
        -H "Authorization: Bearer $ADMIN_TOKEN" | \
        python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || true)
fi

if [ -z "$ROLE_ID" ]; then
    echo "      WARNING: Could not create or find sandbox role. Generating token for admin."
    ROLE_ID=""
fi

# Generate static API key
echo "      Generating static API key..."
SANDBOX_TOKEN="sandbox_dev_token_$(openssl rand -hex 16)"

# Create the user with the static token via direct DB (Directus API for static tokens is limited)
# For sandbox purposes, we use the admin token and document it
echo ""
echo "      Sandbox Admin API Token (use this for API calls):"
echo "      $ADMIN_TOKEN"
echo ""

# ---------------------------------------------------------------
# 3. Import Metabase dashboard JSON templates
# ---------------------------------------------------------------
echo "[3/5] Importing Metabase dashboard templates..."
DASHBOARD_DIR="/dashboards"

if [ -d "$DASHBOARD_DIR" ]; then
    for dashboard_file in "$DASHBOARD_DIR"/*.json; do
        [ -f "$dashboard_file" ] || continue
        fname=$(basename "$dashboard_file")
        echo "      Found: $fname"
    done
    echo "      Dashboard templates available in $DASHBOARD_DIR"
    echo "      (Import via Metabase UI or API after setup)"
else
    echo "      No dashboard directory found at $DASHBOARD_DIR — skipping."
fi

# ---------------------------------------------------------------
# 4. Seed sample farm data
# ---------------------------------------------------------------
echo "[4/5] Seeding sample farm data..."

psql -U "${PGUSER:-kokonut}" -d "${PGDATABASE:-kokonut_intelligence}" -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}" << 'SEED_SQL'

-- Sample Location
INSERT INTO location (id, name, slug, description, country, region, sub_region, timezone, latitude, longitude, baseline_revenue, baseline_asset_value, baseline_cash_flow, status)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'Kokonut Demo Farm — Costa Rica',
    'costa-rica-demo',
    'Sandbox demo farm in Guanacaste, Costa Rica. Regenerative mixed-crop operation.',
    'Costa Rica',
    'Guanacaste',
    'Liberia',
    'America/Costa_Rica',
    10.6330,
    -85.4407,
    125000.00,
    340000.00,
    42000.00,
    'active'
) ON CONFLICT (slug) DO NOTHING;

-- Sample Farm
INSERT INTO farm (id, location_id, name, slug, description, farm_type, total_area, area_unit, status)
VALUES (
    'b1f0bc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'Finca El Naranjo',
    'finca-el-naranjo',
    'Mixed agroforestry plot with shade-grown coffee and cacao understory.',
    'agroforestry',
    45.0,
    'hectares',
    'active'
) ON CONFLICT (slug) DO NOTHING;

-- Sample Plots
INSERT INTO plot (id, farm_id, name, slug, description, area, area_unit, soil_type, status)
VALUES
    ('c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'b1f0bc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Plot A — Coffee', 'plot-a-coffee', 'Shade-grown arabica coffee, 3 years old.', 18.0, 'hectares', 'volcanic_loam', 'active'),
    ('c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b1f0bc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Plot B — Cacao', 'plot-b-cacao', 'Trinitario cacao, intercropped with banana.', 15.0, 'hectares', 'clay_loam', 'active'),
    ('c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'b1f0bc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Plot C — Timber', 'plot-c-timber', 'Teak and mahogany agroforestry buffer zone.', 12.0, 'hectares', 'sandy_loam', 'active')
ON CONFLICT (slug) DO NOTHING;

-- Sample Crops
INSERT INTO crop (id, name, scientific_name, crop_category, growing_season_days, expected_yield_per_ha, expected_yield_unit, water_needs)
VALUES
    ('d3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a66', 'Arabica Coffee', 'Coffea arabica', 'tree', 270, 1800, 'kg', 'medium'),
    ('d3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a77', 'Trinitario Cacao', 'Theobroma cacao', 'tree', 365, 2200, 'kg', 'high'),
    ('d3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a88', 'Plantain', 'Musa paradisiaca', 'fruit', 300, 12000, 'kg', 'high')
ON CONFLICT DO NOTHING;

-- Sample Crop Cycles
INSERT INTO crop_cycle (id, plot_id, crop_id, location_id, cycle_name, season, planting_date, expected_harvest_date, expected_yield, expected_yield_unit, expected_price_per_unit, expected_revenue, status)
VALUES
    ('e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380a99', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'd3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a66', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Coffee 2026A', 'wet', '2026-03-01', '2026-11-30', 32400, 'kg', 4.50, 145800.00, 'active'),
    ('e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380b00', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'd3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a77', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Cacao 2026A', 'wet', '2026-02-15', '2027-02-15', 33000, 'kg', 3.80, 125400.00, 'active'),
    ('e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'd3b0bc99-9c0b-4ef8-bb6d-6bb9bd380a88', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Plantain 2026A', 'wet', '2026-01-15', '2026-11-15', 180000, 'kg', 0.65, 117000.00, 'harvesting')
ON CONFLICT DO NOTHING;

-- Sample Harvest Events
INSERT INTO harvest_event (id, crop_cycle_id, plot_id, location_id, harvest_date, quantity, unit, quality_grade, destination, status)
VALUES
    ('f5d0bc99-9c0b-4ef8-bb6d-6bb9bd380d22', 'e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380a99', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '2026-06-01', 4200, 'kg', 'A', 'wet_mill', 'verified'),
    ('f5d0bc99-9c0b-4ef8-bb6d-6bb9bd380d33', 'e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380a99', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '2026-06-15', 3800, 'kg', 'A', 'wet_mill', 'verified'),
    ('f5d0bc99-9c0b-4ef8-bb6d-6bb9bd380d44', 'e4c0bc99-9c0b-4ef8-bb6d-6bb9bd380b00', 'c2a0bc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '2026-06-20', 5500, 'kg', 'A', 'fermentery', 'verified')
ON CONFLICT DO NOTHING;

-- Sample Expense Categories (already seeded by seed.sh, but ensure presence)
INSERT INTO expense_category (name, code, is_direct, sort_order) VALUES
    ('Seeds & Planting Material', 'SEED', true, 1),
    ('Fertilizer & Soil Amendments', 'FERT', true, 2),
    ('Pest & Disease Control', 'PEST', true, 3),
    ('Irrigation & Water', 'IRRI', true, 4),
    ('Labor - Field', 'LAB-F', true, 5),
    ('Labor - Processing', 'LAB-P', true, 6),
    ('Equipment & Machinery', 'EQUI', true, 8),
    ('Transport & Logistics', 'TRAN', true, 9),
    ('Packaging & Processing', 'PACK', true, 10)
ON CONFLICT (name) DO NOTHING;

-- Sample Expense Events
INSERT INTO expense_event (id, location_id, expense_category_id, expense_date, amount, currency, status, allocation_method, description)
SELECT
    gen_random_uuid(),
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    ec.id,
    d::date,
    (random() * 5000 + 500)::numeric(12,2),
    'USD',
    'approved',
    'direct',
    'Sandbox sample expense — ' || ec.name
FROM expense_category ec
CROSS JOIN generate_series('2026-01-01'::date, '2026-06-30'::date, '14 days') d
WHERE ec.code IN ('SEED', 'FERT', 'PEST', 'IRRI', 'LAB-F')
ON CONFLICT DO NOTHING;

-- Sample Expense Allocations
INSERT INTO crop_cost_allocation (id, expense_event_id, crop_cycle_id, allocation_method, allocated_amount, allocation_pct)
SELECT
    gen_random_uuid(),
    ee.id,
    (SELECT id FROM crop_cycle ORDER BY random() LIMIT 1),
    'direct',
    ee.amount,
    1.0
FROM expense_event ee
WHERE ee.location_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
  AND ee.status = 'approved'
LIMIT 20
ON CONFLICT DO NOTHING;

-- Sample Attestation Schema
INSERT INTO attestation_schema (id, schema_uid, name, description, schema_text, chain, active)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    '0x7d8b5c3a2e1f9d4b6c8a0e2f5d7b3c1a9e4f6d8b2c5a7e0f3d6b9c1a4e7f0d2',
    'Harvest MRV Claim',
    'Verifies that a harvest event occurred with stated quantity and quality.',
    'uint256 harvestId, uint256 quantityKg, uint8 qualityGrade, address farmer, uint256 timestamp',
    'optimism',
    true
) ON CONFLICT (schema_uid) DO NOTHING;

-- Sample Attestation Record
INSERT INTO attestation_record (id, attestation_uid, schema_id, claim_type, subject_id, subject_type, claim_data, status, chain)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    '0xattest_sandbox_sample_001',
    '11111111-1111-1111-1111-111111111111',
    'mrv',
    'f5d0bc99-9c0b-4ef8-bb6d-6bb9bd380d22',
    'harvest_event',
    '{"harvestId": 1, "quantityKg": 4200, "qualityGrade": 1, "farmer": "0x1234...abcd", "timestamp": 1748793600}',
    'attested',
    'optimism'
) ON CONFLICT DO NOTHING;

SEED_SQL

echo "      Sample farm data seeded."

# ---------------------------------------------------------------
# 5. Print connection info
# ---------------------------------------------------------------
echo ""
echo "[5/5] Sandbox ready!"
echo ""
echo "============================================"
echo "  Connection Info"
echo "============================================"
echo ""
echo "  Directus Admin UI:  http://localhost:8055"
echo "  Directus API:       http://localhost:8055/items/{collection}"
echo "  Admin Email:        $ADMIN_EMAIL"
echo ""
echo "  Metabase UI:        http://localhost:3001"
echo ""
echo "  PostgreSQL:         localhost:5432"
echo "  ClickHouse:         localhost:8123"
echo ""
echo "  Admin API Token:    (see above, use as Bearer token)"
echo ""
echo "  Quick test:"
echo "    curl -H 'Authorization: Bearer $ADMIN_TOKEN' \\"
echo "      http://localhost:8055/items/location"
echo ""
echo "============================================"
