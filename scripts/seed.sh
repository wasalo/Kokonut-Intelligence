#!/usr/bin/env bash
# ============================================================
# seed.sh — Load pilot farm data into the platform
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

DB_CONTAINER="kokonut-intelligence-database-1"

# Wait for database
echo "Waiting for PostgreSQL..."
until docker exec "$DB_CONTAINER" pg_isready -U kokonut -d kokonut_intelligence > /dev/null 2>&1; do
    sleep 2
done
echo "PostgreSQL is ready."

# Apply schema files
echo ""
echo "Applying schema files..."

SCHEMA_DIR="$PROJECT_DIR/schemas/postgres"
for schema_file in "$SCHEMA_DIR"/*.sql; do
    filename=$(basename "$schema_file")
    echo "  Applying: $filename"
    docker exec -i "$DB_CONTAINER" psql -U kokonut -d kokonut_intelligence < "$schema_file"
done

echo ""
echo "Schema applied successfully."

# Seed expense categories
echo ""
echo "Seeding expense categories..."
docker exec -i "$DB_CONTAINER" psql -U kokonut -d kokonut_intelligence << 'SQL'
INSERT INTO expense_category (name, code, is_direct, sort_order) VALUES
    ('Seeds & Planting Material', 'SEED', true, 1),
    ('Fertilizer & Soil Amendments', 'FERT', true, 2),
    ('Pest & Disease Control', 'PEST', true, 3),
    ('Irrigation & Water', 'IRRI', true, 4),
    ('Labor - Field', 'LAB-F', true, 5),
    ('Labor - Processing', 'LAB-P', true, 6),
    ('Labor - Admin', 'LAB-A', false, 7),
    ('Equipment & Machinery', 'EQUI', true, 8),
    ('Transport & Logistics', 'TRAN', true, 9),
    ('Packaging & Processing', 'PACK', true, 10),
    ('Utilities', 'UTIL', false, 11),
    ('Rent & Land', 'RENT', false, 12),
    ('Insurance', 'INS', false, 13),
    ('Marketing & Sales', 'MARK', false, 14),
    ('Professional Services', 'PROF', false, 15),
    ('Maintenance & Repairs', 'MAINT', true, 16),
    ('Bioinputs & Compost', 'BIO', true, 17),
    ('Other Direct Costs', 'OTH-D', true, 18),
    ('Other Shared Costs', 'OTH-S', false, 19)
ON CONFLICT (name) DO NOTHING;
SQL

echo "Expense categories seeded."

# Seed metric definitions
echo ""
echo "Seeding metric definitions..."
docker exec -i "$DB_CONTAINER" psql -U kokonut -d kokonut_intelligence << 'SQL'
INSERT INTO metric_definition (metric_key, display_name, description, formula, source_tables, inclusion_rules, exclusion_rules, unit, data_type, update_frequency) VALUES
    ('crop_revenue', 'Crop Revenue', 'Gross crop sales recognized for a crop and period', 'SUM(sales_event.total_amount) WHERE status = verified', ARRAY['sales_event', 'crop_cycle'], 'Only verified sales', 'Exclude returns and cancelled sales', 'currency', 'currency', 'daily'),
    ('net_crop_revenue', 'Net Crop Revenue', 'Crop revenue minus returns, discounts, and rejected sales', 'crop_revenue - SUM(return_amount + discount_amount)', ARRAY['sales_event', 'crop_cycle'], 'Only verified sales', 'None', 'currency', 'currency', 'daily'),
    ('direct_crop_cost', 'Direct Crop Cost', 'Costs directly attributable to a crop/cycle', 'SUM(expense_event.amount) WHERE crop_cycle_id IS NOT NULL AND allocation_method = direct', ARRAY['expense_event', 'crop_cycle'], 'Only approved/paid expenses with direct allocation', 'Exclude shared costs', 'currency', 'currency', 'daily'),
    ('allocated_shared_cost', 'Allocated Shared Cost', 'Shared costs allocated using governed allocation rules', 'SUM(crop_cost_allocation.allocated_amount)', ARRAY['crop_cost_allocation', 'expense_event'], 'Only approved allocations', 'None', 'currency', 'currency', 'daily'),
    ('crop_noi', 'Crop NOI', 'Net crop revenue minus direct crop costs minus allocated shared operating costs', 'net_crop_revenue - direct_crop_cost - allocated_shared_cost', ARRAY['noi_snapshot', 'crop_cycle'], 'Only verified data', 'None', 'currency', 'currency', 'daily'),
    ('loss_rate_pct', 'Loss Rate %', '1 - (saleable output / harvested output)', '1 - (net_harvest / gross_harvest)', ARRAY['harvest_event', 'crop_cycle'], 'All harvest events', 'Exclude unrecoverable losses marked as force majeure', 'percentage', 'percentage', 'daily'),
    ('operating_margin_pct', 'Operating Margin %', 'Operating income / net sales', 'crop_noi / net_crop_revenue * 100', ARRAY['noi_snapshot', 'crop_cycle'], 'Only crops with positive revenue', 'None', 'percentage', 'percentage', 'daily'),
    ('baseline_revenue', 'Baseline Revenue', 'Revenue before Kokonut intervention or onboarding', 'location.baseline_revenue', ARRAY['location'], 'Set at onboarding', 'None', 'currency', 'currency', 'once'),
    ('baseline_asset_value', 'Baseline Asset Value', 'Estimated starting asset or productive value', 'location.baseline_asset_value', ARRAY['location'], 'Set at onboarding', 'None', 'currency', 'currency', 'once'),
    ('baseline_cash_flow', 'Baseline Cash Flow', 'Pre-intervention net cash flow', 'location.baseline_cash_flow', ARRAY['location'], 'Set at onboarding', 'None', 'currency', 'currency', 'once'),
    ('value_flowed', 'Value Flowed', 'Verified value attributable to Kokonut activity, excluding failed rounds, returned funds, and excluded fees', 'SUM(value_flow_event.amount) WHERE verified = true AND is_excluded = false', ARRAY['value_flow_event'], 'Only verified flows', 'Exclude failed rounds, returned funds, excluded fees, double-counted flows', 'currency', 'currency', 'weekly'),
    ('wallet_retention', 'Wallet Retention', 'Wallet active in current period and at least one prior defined period', 'COUNT(DISTINCT wallet_id) WHERE active_in_current AND active_in_prior', ARRAY['wallet_activity_event', 'wallet_profile'], 'Active wallets', 'None', 'count', 'count', 'monthly'),
    ('digital_lego_usage', 'Digital Lego Usage', 'Verified interaction with tracked Web3 components', 'COUNT(DISTINCT protocol_id) WHERE verified = true', ARRAY['digital_lego_usage'], 'Verified interactions only', 'None', 'count', 'count', 'weekly'),
    ('soil_carbon_delta', 'Soil Carbon Delta', 'Soil carbon after intervention minus baseline', 'after_measurement.carbon_tonnes_per_ha - baseline.carbon_tonnes_per_ha', ARRAY['soil_carbon_measurement'], 'Verified measurements only', 'Exclude model estimates where lab data available', 'tonnes_per_ha', 'numeric', 'quarterly'),
    ('biodiversity_delta', 'Biodiversity Delta', 'Species count after intervention minus baseline', 'after_observation.species_count - baseline.species_count', ARRAY['species_observation'], 'Verified observations', 'None', 'count', 'count', 'quarterly'),
    ('attestation_coverage', 'Attestation Coverage', 'Attested claims / eligible publishable claims', 'COUNT(attested) / COUNT(eligible) * 100', ARRAY['attestation_record', 'mrv_claim'], 'All eligible claims', 'None', 'percentage', 'percentage', 'monthly')
ON CONFLICT (metric_key) DO NOTHING;
SQL

echo "Metric definitions seeded."

echo ""
echo "=== Seed Complete ==="
echo ""
echo "Next steps:"
echo "  1. Access Directus at http://localhost:8055"
echo "  2. Create your admin account (if not auto-created)"
echo "  3. Import Baserow data: python migrations/baserow_to_postgres/migrate.py --config config.json --dry-run"
echo "  4. Configure Metabase at http://localhost:3000"
echo ""
