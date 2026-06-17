# Metabase Dashboards

This directory contains SQL queries and JSON import templates for Metabase dashboards.

## Dashboards

### 0. Location Overview
- **File**: `00_location_overview.json`
- **SQL**: `sql/00_location_overview.sql`
- **Description**: Per-location KPIs: baselines vs actuals, crop cycles, revenue, losses, and expenses

### 1. Farm Operations
- **File**: `01_farm_operations.json`
- **SQL**: `sql/01_farm_operations.sql`
- **Description**: Overview of farm operations including harvest volumes and activity counts

### 2. Crop NOI
- **File**: `02_crop_noi.json`
- **SQL**: `sql/02_crop_noi.sql`
- **Description**: Net Operating Income analysis by crop with revenue, costs, and margins

### 3. Expense Tracker
- **File**: `03_expense_tracker.json`
- **SQL**: `sql/03_expense_tracker.sql`
- **Description**: Expense analysis by category with direct vs shared cost breakdown

### 4. Harvest & Sales
- **File**: `04_harvest_sales.json`
- **SQL**: `sql/04_harvest_sales.sql`
- **Description**: Monthly harvest volumes and sales revenue analysis by crop

### 5. Loss Rate
- **File**: `05_loss_rate.json`
- **SQL**: `sql/05_loss_rate.sql`
- **Description**: Loss rate analysis by crop and loss type with financial impact

### 6. Eagle View (NEW)
- **File**: `06_eagle_view.json`
- **SQL**: `sql/06_eagle_view_overview.sql` through `sql/12_eagle_view_monthly_trend.sql`
- **Description**: Platform-wide overview: KPIs, financials, harvest, environment, attestations, sensors, and monthly trends

## Usage

### Option 1: Manual SQL Queries
1. Open Metabase at http://localhost:3001
2. Go to "New" → "Native Query"
3. Select the "Kokonut Intelligence" database
4. Paste the SQL query from the `sql/` directory
5. Run the query and save it as a question
6. Create a new dashboard and add the saved questions

### Option 2: JSON Import (via API)
1. Use the Metabase API to import the JSON templates
2. Example API call:
   ```bash
   curl -X POST http://localhost:3001/api/dashboard \
     -H "Content-Type: application/json" \
     -H "X-Metabase-Session: YOUR_SESSION_ID" \
     -d @01_farm_operations.json
   ```

## Database Connection
- **Database**: Kokonut Intelligence (ID: 2)
- **Schema**: `public` (all tables live in the `public` schema)
- **Tables**: All tables are accessible without a schema prefix

## Notes
- All queries use bare table names (e.g., `farm`, `harvest_event`) — no schema prefix needed
- Queries filter out rejected records by default
- NULL values are handled with COALESCE
- Dates are truncated to month level for trend analysis
