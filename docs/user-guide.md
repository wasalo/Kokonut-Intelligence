# Kokonut Intelligence — User Guide

Welcome to the Kokonut Intelligence Platform. This guide walks you through using the platform day-to-day — from logging in and entering data to viewing dashboards and running analytics.

---

## Table of Contents

1. [Welcome](#1-welcome--what-is-kokonut-intelligence)
2. [Getting Started](#2-getting-started)
3. [Your Role — What You Can Do](#3-your-role--what-you-can-do)
4. [The Workflow — How Records Move](#4-the-workflow--how-records-move)
5. [Entering Data — Step-by-Step](#5-entering-data--step-by-step)
6. [Understanding Validation & AI Assistance](#6-understanding-validation--ai-assistance)
7. [Viewing Dashboards](#7-viewing-dashboards)
8. [Partner Access — What External Partners See](#8-partner-access--what-external-partners-see)
9. [Running Analytics](#9-running-analytics)
10. [Exporting Data](#10-exporting-data)
11. [Working with the SDK](#11-working-with-the-sdk)
12. [Understanding Attestations](#12-understanding-attestations)
13. [Troubleshooting](#13-troubleshooting)
14. [Glossary](#14-glossary)

---

## 1. Welcome — What is Kokonut Intelligence?

Kokonut Intelligence is an open-source platform for managing regenerative farm operations. It brings together operational data (harvests, expenses, sales), environmental data (soil, weather, sensors, remote sensing), and financial performance into a single governed system with built-in verification and reporting.

**Who this guide is for:**

| Audience | What to read |
|----------|-------------|
| Field workers entering daily data | Sections 2–6 |
| Supervisors and managers approving records | Sections 2–6 |
| Finance staff reviewing expenses and sales | Sections 2–6 |
| Analysts querying verified data | Sections 2, 7, 10 |
| External partners (buyers, funders, vendors) | Sections 2, 7–8 |
| Developers building integrations | Sections 9–12 |
| Platform administrators | All sections |

**What you'll learn:**

- How to log in and navigate the platform
- What your role allows you to do
- How to enter, submit, and approve records
- How to view dashboards and reports
- How to run analytics and export data

---

## 2. Getting Started

### Logging In

1. Open your browser and go to `http://localhost:8055` (or your organization's Directus URL).
2. Enter your email and password provided by your administrator.
3. You'll land on the Directus home screen.

![Directus home](images/directus-home.png)

### Navigating the Interface

The Directus interface has three main areas:

- **Left sidebar** — Lists all collections (tables) you have access to. Click a collection name to browse its records.
- **Main content area** — Shows the selected collection's records in a table, or a single record's detail view.
- **Top bar** — Contains search, filters, your user menu, and the Dashboard link.

**Key navigation actions:**

| Action | How |
|--------|-----|
| Browse a collection | Click its name in the left sidebar |
| Create a new record | Click the `+` button in the top right of a collection view |
| Filter records | Click the filter icon and add conditions |
| Edit a record | Click any row in the table, then click the edit (pencil) icon |
| Export data | Click the `...` menu → Export |

### Your User Menu

Click your avatar/name in the top right corner to:

- View your profile (including your assigned role and location)
- Access the Dashboard module (if you have permission)
- Log out

---

## 3. Your Role — What You Can Do

Every user is assigned a **role** that determines what they can see and do. Your administrator sets your role when creating your account.

### Field Worker

**Icon:** 🌾 agriculture

**What you can do:**
- Create new records: farm activities, harvests, expenses, sales, losses, labor events, field notes
- Edit your own records while they are in **draft** status
- View your own records

**What you cannot do:**
- See records from other locations
- Submit records for approval (that's your Supervisor's job)
- Edit records that have already been submitted

**Your typical day:**
1. Log in to Directus
2. Navigate to the collection for what you're recording (e.g., `harvest_event`)
3. Click `+` to create a new record
4. Fill in the fields — the system will auto-calculate costs and validate your entries
5. Save the record (it stays in **draft** status)
6. Your Supervisor will review and submit it

### Supervisor

**Icon:** 👁 supervisor_account

**What you can do:**
- **Read** all records across all locations
- **Submit** records for approval (change status from draft → submitted)
- View the full workflow history

**What you cannot do:**
- Edit record data (only Field Workers can edit drafts)
- Verify or approve records (that's the Manager's job)

**Your typical day:**
1. Log in and review the `submitted` queue — records waiting for approval
2. Check that records from your team are complete and accurate
3. Submit draft records that are ready for review (change status to **submitted**)
4. If a record needs correction, ask the Field Worker to fix it (it stays in draft)

### Manager

**Icon:** 👤 supervised_user_circle

**What you can do:**
- **Read** all records across all locations
- **Verify** records (change status from submitted → verified)
- **Reject** records with a reason (change status from submitted → rejected)
- Publish records for operational data (verified → published)

**What you cannot do:**
- Verify expenses or sales (that's the Finance role's job)
- Edit record data

**Your typical day:**
1. Log in and review the **submitted** queue
2. Review each record for accuracy and completeness
3. **Approve** (verify) records that pass review — they become verified
4. **Reject** records that need correction — provide a reason so the Field Worker knows what to fix
5. **Publish** verified records to make them available to dashboards and analysts

### Finance

**Icon:** 💰 account_balance

**What you can do:**
- **Read** all records across all locations, including financial summaries (NOI snapshots)
- **Verify** expenses and sales (submitted → verified)
- **Reject** expenses and sales with a reason
- **Publish** verified expenses and sales

**What you cannot do:**
- Verify operational records (farm activities, harvests, losses — that's the Manager)
- Edit record data

**Your typical day:**
1. Log in and review submitted expenses and sales
2. Check amounts, categories, and receipts
3. **Approve** valid expenses and sales
4. **Reject** entries with discrepancies and provide a reason
5. Review NOI snapshots and financial summaries

### Analyst

**Icon:** 📊 analytics

**What you can do:**
- **Read** verified and published records (read-only)
- Run queries, exports, and reports
- View all dashboards

**What you cannot do:**
- Edit, create, or delete any records
- Submit or approve records

**Your typical day:**
1. Log in and browse verified/published data
2. Use the Metabase dashboards (`http://localhost:3001`) for visual analysis
3. Export data to CSV/JSON for deeper analysis
4. Run reports via the CLI or SDK

### Administrator

**What you can do:**
- Full access to everything
- Manage users, roles, and permissions
- Create and modify the database schema
- Deploy contracts and manage EAS attestations
- Create partner user accounts

---

## 4. The Workflow — How Records Move

Every operational record follows a **4-stage lifecycle**. This ensures data goes through proper review before it's published to dashboards and reports.

```
  ┌─────────┐
  │  DRAFT   │  ← Record created (Field Worker or Agent)
  └────┬────┘
       │
       ▼ submit
  ┌──────────┐
  │ SUBMITTED │  ← Waiting for review
  └────┬─────┘
       │
       ├──▶ verify ──▶ ┌──────────┐
       │               │ VERIFIED  │  ← Approved, ready to publish
       │               └────┬─────┘
       │                    │
       │                    ▼ publish
       │               ┌───────────┐
       │               │ PUBLISHED  │  ← Final state (available to dashboards)
       │               └───────────┘
       │
       └──▶ reject ──▶ ┌──────────┐
                       │ REJECTED  │  ← Needs correction
                       └────┬─────┘
                            │
                            ▼ rework
                       ┌─────────┐
                       │  DRAFT   │  ← Back to editing
                       └─────────┘
```

### Who Can Do What

| Transition | Who can do it |
|-----------|--------------|
| Draft → Submitted | Any authenticated user |
| Submitted → Verified | Manager, Supervisor (operational records) or Finance (expenses/sales) |
| Submitted → Rejected | Manager, Supervisor (operational records) or Finance (expenses/sales) |
| Rejected → Draft | Any authenticated user (rework) |
| Verified → Published | Manager or Finance |

### What Happens at Each Stage

| Stage | What it means | Who sees it |
|-------|--------------|-------------|
| **Draft** | Record is being created or edited. Not yet reviewed. | Creator + Supervisor + Manager |
| **Submitted** | Record is ready for review. Waiting in the approval queue. | Supervisor + Manager + Finance |
| **Verified** | Record has been reviewed and approved. Ready to publish. | Manager + Analyst + dashboards |
| **Rejected** | Record needs correction. A reason is provided. | Creator (to fix and re-submit) |
| **Published** | Record is final. Available to all dashboards and reports. | Everyone (read-only) |

### Handling Rejections

When a record is rejected:

1. The system sets `rejected_by` and records the rejection reason
2. The record status changes to **rejected**
3. The creator can see the rejection reason in the record's workflow history
4. To fix: change the status back to **draft**, edit the record, and re-submit

### Audit Trail

Every status change is automatically logged to the `workflow_history` table with:
- Who made the change
- When it happened
- What the previous and new status are
- Any notes or rejection reason

---

## 5. Entering Data — Step-by-Step

This section covers how to enter each type of record through the Directus interface.

### Farm Activity

**Purpose:** Log daily farm work — planting, weeding, irrigation, spraying, harvesting.

1. Click **farm_activity** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **activity_type** — Select from: planting, weeding, irrigation, spraying, harvesting, fertilizing, pruning, other
   - **activity_date** — When the work was done
   - **description** — What was done
   - **labor_hours** — Hours worked (optional)
   - **materials_used** — What materials were used (optional)
   - **plot_id** — Which plot this activity was for
4. Click **Save**

The record starts in **draft** status.

### Harvest Event

**Purpose:** Record a harvest with quantity, quality, and loss tracking.

1. Click **harvest_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **harvest_date** — When the harvest happened
   - **quantity** — How much was harvested (in kg or units)
   - **unit** — kg, tonnes, bags, etc.
   - **quality_grade** — A, B, C, or reject
   - **destination** — Where the harvest went
   - **loss_amount** — How much was lost (if any)
   - **loss_reason** — Why the loss occurred (pest, disease, weather, etc.)
   - **plot_id** — Which plot was harvested
   - **crop_cycle_id** — Which crop cycle this belongs to
4. Click **Save**

**What gets auto-calculated:**
- If you enter a loss amount, the system can calculate `loss_estimated_value` based on the crop's price

### Expense Event

**Purpose:** Record a purchase or cost.

1. Click **expense_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **expense_date** — When the expense occurred
   - **description** — What was purchased (e.g., "Bought 50kg fertilizer")
   - **amount** — How much it cost
   - **vendor** — Who you bought it from
   - **is_capex** — Is this a capital expenditure? (Check if yes)
4. Click **Save**

**What gets auto-calculated:**
- **category** — The system auto-suggests a category based on your description:
  - "fertilizer" → Fertilizer & Amendments
  - "seed" → Seeds & Planting Material
  - "pesticide" → Pest & Disease Control
  - "irrigation" → Water & Irrigation
  - "tractor" → Equipment & Machinery
  - "transport" → Transport & Logistics
  - "labor" → Labor & Wages
  - And 30+ more keyword rules

**Validation rules:**
- Amount must be greater than 0
- Amount cannot exceed $100,000 (flagged as suspicious)
- Date cannot be in the future
- Date cannot be more than 1 year old

### Sales Event

**Purpose:** Record a sale to a buyer.

1. Click **sales_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **sale_date** — When the sale happened
   - **buyer** — Who you sold to
   - **quantity** — How much was sold
   - **price_per_unit** — Price per unit
   - **unit** — kg, tonnes, bags, etc.
   - **payment_status** — paid, pending, partial, overdue
4. Click **Save**

**What gets auto-calculated:**
- **total_amount** — quantity × price_per_unit
- **net_amount** — total_amount minus returns minus discounts

**Validation rules:**
- Total amount must be greater than 0
- Total amount cannot exceed $500,000 (flagged as suspicious)

### Loss / Incident Event

**Purpose:** Record crop losses from pests, weather, disease, or other causes.

1. Click **loss_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **loss_date** — When the loss occurred
   - **loss_type** — pest, disease, weather, flood, drought, theft, other
   - **quantity** — How much was lost
   - **severity** — low, medium, high, critical
   - **mitigation** — What was done about it
   - **estimated_value** — Financial impact (optional, auto-calculated if crop price is available)

### Labor Event

**Purpose:** Track worker hours and costs.

1. Click **labor_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **worker_name** — Who worked
   - **work_date** — When
   - **hours_worked** — How many hours
   - **hourly_rate** — Pay rate
   - **role** — What they did

**What gets auto-calculated:**
- **total_cost** — hours_worked × hourly_rate

### Field Note

**Purpose:** Record observations, photos, or free-form notes from the field.

1. Click **field_note** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **note_date** — When
   - **note_type** — observation, issue, recommendation, other
   - **title** — Short summary
   - **content** — Detailed description
   - **images** — Photo URLs (if any)
   - **tags** — Searchable tags

**What gets auto-calculated:**
- If content is longer than 200 characters, the system auto-generates a summary from the first sentence

---

## 6. Understanding Validation & AI Assistance

The platform includes built-in validation rules that run automatically when you save a record. These are rule-based (no AI/LLM) and help catch common errors.

### Expense Auto-Categorization

When you enter a description for an expense, the system matches keywords to suggest a category:

| Keywords in description | Suggested category |
|------------------------|-------------------|
| seed, seeds, planting, nursery | Seeds & Planting Material |
| fertilizer, compost, manure, organic matter | Fertilizer & Amendments |
| pesticide, fungicide, herbicide, spray | Pest & Disease Control |
| irrigation, water, pump, drip | Water & Irrigation |
| tractor, equipment, machine, repair | Equipment & Machinery |
| transport, truck, delivery, fuel | Transport & Logistics |
| labor, wages, worker, crew | Labor & Wages |
| packaging, bag, box, label | Packaging & Processing |
| soil, pH, nitrogen, potassium | Soil & Nutrients |
| energy, solar, electricity, power | Energy & Power |

If the system suggests the wrong category, you can manually override it.

### Amount Validation

- Expenses must be greater than $0 and less than $100,000
- Sales must be greater than $0 and less than $500,000
- Amounts outside these ranges are flagged as **suspicious** for reviewer attention

### Harvest Quantity Validation

- If the expected yield for the crop cycle is known, the system compares your harvest quantity
- Harvests **above 150%** or **below 10%** of expected yield are flagged as unusual

### Date Validation

- No future dates allowed for expenses or activities
- Expenses older than 1 year are flagged

### Auto-Calculations

| Field | Calculation |
|-------|------------|
| Sales `total_amount` | quantity × price_per_unit |
| Sales `net_amount` | total_amount − return_amount − discount_amount |
| Labor `total_cost` | hours_worked × hourly_rate |
| Loss `estimated_value` | loss_quantity × crop_price (when available) |

---

## 7. Viewing Dashboards

### Directus Dashboards

To access the Dashboard module:

1. Click the **Dashboard** icon in the left sidebar (or go to `http://localhost:8055/admin/content`)
2. Select the dashboard relevant to your role

**Available dashboards by role:**

| Role | Dashboard | What you see |
|------|-----------|-------------|
| Operator | Operations Overview | Active crop cycles, pending tasks, revenue, alerts, sensor data, weather, NDVI trend |
| Buyer | Buyer Dashboard | Production summary, upcoming harvests, quality grades, sales history, revenue trend |
| Funder | Funder Dashboard | Financial performance, NOI trend, cost breakdown, forecasts, impact attestations |
| Vendor | Vendor Dashboard | Purchase summary, history, demand forecast, payment status, category breakdown |

### Metabase Dashboards

Access Metabase at `http://localhost:3001` and log in with your credentials.

**6 operational dashboards:**

#### 1. Farm Operations
Shows an overview of all farms: plot count, active crop cycles, total harvest, and activity counts.

#### 2. Crop NOI
Net Operating Income analysis per crop cycle — revenue, direct costs, operating margin, and harvest metrics.

#### 3. Expense Tracker
Expenses broken down by category with direct vs shared cost classification, transaction counts, and averages.

#### 4. Harvest & Sales
Monthly harvest volumes and sales revenue analysis by crop with price trends.

#### 5. Loss Rate
Loss analysis by crop and loss type — loss rate percentage, financial impact, and affected crop cycles.

#### 6. Eagle View
The flagship platform-wide overview with 8 cards:
- Platform statistics (locations, farms, plots, partners, staff)
- Financial summary (revenue, costs, NOI, margin)
- Harvest & loss by crop
- Monthly revenue trend (12-month line chart)
- Attestation coverage
- Sensor & alert status
- Environmental health (soil carbon, biodiversity, NDVI)
- Expense breakdown (pie chart)

![Eagle View dashboard](images/eagle-view-dashboard.png)

### Accessing Dashboards

| Dashboard | URL | Login |
|-----------|-----|-------|
| Directus | `http://localhost:8055` | Your Directus credentials |
| Metabase | `http://localhost:3001` | Your Metabase credentials |

---

## 8. Partner Access — What External Partners See

Partners (buyers, funders, vendors, operators) have restricted access through **row-level security** — they can only see data related to their own transactions.

### How Partner Access Works

1. Your administrator creates a partner user account and assigns them a partner role
2. The partner logs in and sees only their own data
3. They cannot see other partners' transactions, financial details, or internal operations

### Buyer View

**What a buyer sees:**
- Harvests destined for them (quantity, quality, date)
- Sales records where they are the buyer
- Production summaries and quality grade distributions
- Revenue trends for their purchases

**What a buyer cannot see:**
- Other buyers' transactions
- Internal costs, expenses, or financial details
- Sensor data or environmental measurements

### Funder View

**What a funder sees:**
- Aggregated financial performance (NOI, revenue, costs)
- Forecast scenarios and projections
- Published impact attestations (MRV, environmental)
- Ecological outcomes (NDVI, soil carbon trends)

**What a funder cannot see:**
- Individual buyer or vendor transactions
- Internal operational details
- Raw sensor data

### Vendor View

**What a vendor sees:**
- Purchase orders where they are the vendor
- Payment status and history
- Upcoming demand forecasts
- Their expense categories

**What a vendor cannot see:**
- Other vendors' transactions
- Farm-level operational details
- Financial summaries beyond their own purchases

### Operator View

**What an operator sees:**
- Full operational data for their assigned locations
- Crop cycles, activities, harvests, sensors, weather
- Financial summaries (revenue, NOI)
- Alerts and notifications

**What an operator cannot see:**
- Other operators' locations (unless explicitly assigned)

### Setting Up a Partner User (Admin Task)

1. Log in as Admin to Directus
2. Go to **User Directory** → **Create User**
3. Enter the partner's email and name
4. Assign them the appropriate partner role (Buyer, Funder, Vendor, or Operator)
5. Set their `partner_id` or `assigned_locations` to scope their data access
6. The partner receives their login credentials and can access the platform

---

## 9. Running Analytics

### Fortune 500 Farm Scoring

The Fortune 500 scoring system ranks farms on a 0–1000 scale across 4 pillars:

| Pillar | Weight | What it measures |
|--------|--------|-----------------|
| Financial | 45% | NOI, operating margin, revenue per hectare, loss rate, cost efficiency |
| Ecological | 25% | NDVI, soil organic matter, data completeness, remote sensing coverage |
| Governance | 15% | Attestation count, governance events, treasury activity, metric definitions |
| Growth | 15% | Yield improvement, revenue growth, data completeness |

**Tiers:**
- **Platinum** (800+) — Top-performing regenerative farm
- **Gold** (600+) — Strong performance across all pillars
- **Silver** (400+) — Solid foundation with room for improvement
- **Bronze** (200+) — Early-stage, building data and operations
- **Developing** (<200) — New farm, limited data

**Run scoring:**

```bash
# Score a specific farm
python3 -m services.fortune500.cli --location-id <location-id>

# Rank all farms
python3 -m services.fortune500.cli --all
```

### Revenue Forecasting

Time-series projections with Monte Carlo simulation for uncertainty estimation.

```bash
# Run forecast for 3, 6, or 12 months
python3 -m services.forecast.cli --location-id <location-id>

# Custom horizon and simulations
python3 -m services.forecast.cli --location-id <location-id> \
  --months 12 --simulations 2000

# Compare scenarios
python3 -m services.forecast.cli --location-id <location-id> --compare

# Sensitivity analysis
python3 -m services.forecast.cli --location-id <location-id> --sensitivity
```

**Output:**
- Monthly revenue, NOI, and yield projections with confidence bands
- Best-case, worst-case, and most-likely scenarios
- Historical trend analysis from your harvest and sales data

### Revenue Multiplier Opportunity Map

10-dimension analysis identifying where your farm can generate the most additional revenue:

```bash
# Analyze all dimensions
python3 -m services.revenue_multiplier.cli --location-id <location-id>

# Analyze a specific dimension
python3 -m services.revenue_multiplier.cli --location-id <location-id> \
  --dimension crop_mix

# List all dimensions
python3 -m services.revenue_multiplier.cli --list-dimensions
```

**The 10 dimensions:**
1. Crop mix optimization
2. Loss-rate reduction
3. Buyer/channel selection
4. Value-added processing
5. Web3-funded replication
6. Bioinput production
7. Public-goods funding loops
8. Ecological verification (carbon, biodiversity, impact credits)
9. Partner sponsorship
10. Regional farm clusters

Each dimension returns a USD impact estimate and confidence level.

### Ecological Analytics

```bash
# Soil carbon comparison (baseline vs latest)
python3 -m services.analytics.cli --soil-carbon --location-id <location-id>

# Biodiversity index (Shannon diversity)
python3 -m services.analytics.cli --biodiversity --location-id <location-id>

# Compare forecast scenarios
python3 -m services.analytics.cli --compare-scenarios --location-id <location-id>

# Sensitivity analysis
python3 -m services.analytics.cli --sensitivity --location-id <location-id>
```

---

## 10. Exporting Data

### Quick Export (CLI)

```bash
# Export harvests to CSV
python3 -m services.export.exporter \
  --collection harvest_event --format csv --output exports/

# Export expenses to JSON with filters
python3 -m services.export.exporter \
  --collection expense_event --format json \
  --filter '{"status":"verified"}'

# Export sensor readings from ClickHouse
python3 -m services.export.exporter \
  --collection sensor_readings --format parquet --source clickhouse
```

### Available Formats

| Format | Best for | Notes |
|--------|---------|-------|
| CSV | Spreadsheets, Excel | Universal compatibility |
| JSON | APIs, programming | Preserves nested data |
| Parquet | Analytics, big data | Compressed columnar format (requires pyarrow) |

### Report Generation

```bash
# Farm summary report
python3 -m services.export.report_generator \
  --type farm_summary --location-id <location-id>

# Crop NOI report
python3 -m services.export.report_generator \
  --type crop_noi --location-id <location-id>

# Environmental report
python3 -m services.export.report_generator \
  --type environmental --location-id <location-id>

# List available report types
python3 -m services.export.report_generator --list
```

Reports are stored as snapshots with SHA-256 hashes for verification.

---

## 11. Working with the SDK

### Python SDK

```bash
cd sdk/python && pip install -e .
```

**Quick start:**

```python
from kokonut_sdk import KokonutClient

client = KokonutClient("http://localhost:8055", "your-api-token")

# List farms
farms = client.farms.list()

# Create a harvest event
harvest = client.harvest_events.create({
    "harvest_date": "2025-06-15",
    "quantity": 500,
    "unit": "kg",
    "quality_grade": "A",
    "location_id": "your-location-id",
    "plot_id": "your-plot-id"
})

# Query verified records only
expenses = client.expense_events.list(
    filter={"status": {"_eq": "verified"}},
    sort=["-expense_date"],
    limit=50
)
```

See `sdk/python/examples/` for full examples including workflow lifecycle, batch uploads, and NOI queries.

### JavaScript/TypeScript SDK

```bash
cd sdk/javascript && npm install && npm run build
```

**Quick start:**

```typescript
import { KokonutClient } from '@kokonut/intelligence';

const client = new KokonutClient('http://localhost:8055', 'your-api-token');

// List active crop cycles
const cycles = await client.cropCycleMethods.listActive();

// Create a sensor reading
await client.sensorReadings.create({
    sensor_type: 'soil_moisture',
    value: 32.5,
    unit: 'pct',
    reading_date: new Date().toISOString(),
    device_id: 'your-device-id'
});
```

See `sdk/javascript/examples/` for full examples.

---

## 12. Understanding Attestations

Attestations are verifiable claims published on-chain via the Ethereum Attestation Service (EAS) on Celo.

### Onchain vs Offchain

| Type | Gas cost | Visibility | Use case |
|------|----------|-----------|----------|
| **Onchain** | Paid in CELO | Public on Celo blockchain | High-value claims: MRV results, impact certifications |
| **Offchain** | Free (EIP-712 signature) | Stored off-chain, verifiable via signature | High-frequency: individual sensor readings, routine checks |

### Creating an Attestation (CLI)

```bash
# Check chain configuration
python3 -m services.attestation.cli info --chain celo

# List available schemas
python3 -m services.attestation.cli schema list

# Create an onchain attestation
python3 -m services.attestation.cli attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT_ADDRESS \
  --data '[{"name":"locationId","type":"string","value":"farm-001"}]' \
  --chain celo

# Create a gasless offchain attestation
python3 -m services.attestation.cli offchain-attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT_ADDRESS \
  --data '[{"name":"locationId","type":"string","value":"farm-001"}]' \
  --chain celo

# Query an attestation
python3 -m services.attestation.cli query --uid 0xATTESTATION_UID --chain celo
```

### Kokonut Schemas

| Schema | Use case |
|--------|----------|
| `kokonut-mrv` | MRV claims: location, crop, quantity, evidence |
| `kokonut-impact` | Environmental: soil carbon, biodiversity, NDVI |
| `kokonut-financial` | Financial: NOI, revenue, costs |
| `kokonut-harvest` | Harvest: quantity, quality, date |
| `kokonut-compliance` | Partner compliance and audit trails |

### Private Data

Sensitive data (raw measurements, personal information) is stored off-chain. Only hashes, CIDs, and UIDs are published on-chain. This preserves privacy while maintaining verifiability.

---

## 13. Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Can't log in | Check with your administrator that your account is active and your role is assigned |
| Can't see a collection | Your role may not have access. Ask your administrator. |
| Can't edit a record | The record may not be in **draft** status, or it may not belong to your location |
| Can't submit a record | You may not have permission. Ask a Supervisor to submit it for you. |
| Can't verify a record | Only Managers and Finance can verify. Check your role. |
| Expense category looks wrong | The auto-categorization is keyword-based. Manually override the category if needed. |
| Metabase dashboards not loading | Ensure Metabase is running: `docker compose ps` |
| Directus not accessible | Ensure Directus is running: `docker compose ps` |
| Export fails | Check that the collection name is valid and you have read access |
| Attestation fails | Verify your private key is in `.env` and the chain is accessible |

### Getting Help

- Check the [Architecture Guide](architecture.md) for system overview
- See the [API Reference](api-reference.md) for endpoint details
- Review the [Data Dictionary](data-dictionary.md) for field definitions
- Check the [Attestation Guide](attestation-guide.md) for EAS setup
- Review the [Export Guide](export-guide.md) for export options

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **Attestation** | A verifiable claim published on-chain (EAS) or signed off-chain (EIP-712) |
| **Crop cycle** | The lifecycle of a single crop planting on a specific plot, from planting to harvest |
| **Directus** | The admin UI and API layer for managing the PostgreSQL database |
| **Draft** | Initial status of a record — being created or edited |
| **EAS** | Ethereum Attestation Service — a protocol for on-chain attestations on Celo |
| **Farm** | A named agricultural operation containing one or more plots |
| **Fortune 500** | The platform's farm scoring system (0–1000 scale across 4 pillars) |
| **KokonutResolver** | Smart contract that gates who can create attestations on the platform |
| **Lifecycle** | The 4-stage status flow: draft → submitted → verified → published |
| **Location** | The top-level geographic entity (e.g., a country or region) |
| **MRV** | Measurement, Reporting, and Verification — the process of collecting and validating environmental data |
| **NOI** | Net Operating Income — revenue minus direct costs minus allocated shared costs |
| **Offchain attestation** | A signed claim stored off-chain, verifiable without blockchain gas fees |
| **Onchain attestation** | A claim published to the Celo blockchain, publicly verifiable |
| **Operating margin** | NOI as a percentage of net revenue |
| **Plot** | A specific cultivation area within a farm, with defined boundaries |
| **Published** | Final status — record is available to dashboards and reports |
| **Rejected** | Status indicating a record needs correction, with a reason provided |
| **Row-level security** | Access control that limits which rows a user can see based on their role and assignments |
| **Schema** | The database structure defining tables, columns, and relationships |
| **Submitted** | Status indicating a record is ready for review |
| **Verified** | Status indicating a record has been reviewed and approved |
| **Workflow history** | Audit log of every status change on a record |
