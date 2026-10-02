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
10. [Precision Agriculture](#10-precision-agriculture)
11. [Pest Management](#11-pest-management)
12. [Credit, Marketplace & Carbon](#12-credit-marketplace--carbon)
13. [Cooperative & Digital Finance](#13-cooperative--digital-finance)
14. [Stakeholder & Governance](#14-stakeholder--governance)
15. [Data Governance & Identity](#15-data-governance--identity)
16. [Exporting Data](#16-exporting-data)
17. [Working with the SDK](#17-working-with-the-sdk)
18. [Understanding Attestations](#18-understanding-attestations)
19. [Linked Data & Querying](#19-linked-data--querying)
20. [Troubleshooting](#20-troubleshooting)
21. [Glossary](#21-glossary)

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

### Related Documentation

| Topic | Document |
|-------|----------|
| Daily operations SOP | [Operator Guide](operator-guide.md) |
| Field data collection procedures | [Field Data Collection Guide](field-data-collection-guide.md) |
| Export and report details | [Export Guide](export-guide.md) |
| EAS on-chain verification | [Attestation Guide](attestation-guide.md) |
| Building partner dashboards | [Partner Dashboards](partner-dashboards.md) |
| Review workflow checklist | [Reviewer Guide](reviewer-guide.md) |
| Metric compute vs verify | [Metric Verification](metric-verification.md) |
| Field definitions and formulas | [Data Dictionary](data-dictionary.md) |
| System architecture | [Architecture Guide](architecture.md) |
| API endpoint reference | [API Reference](api-reference.md) |
| Full platform description | [Green Paper](green-paper.md) |

---

## 2. Getting Started

### Logging In

1. Open your browser and go to `https://localhost/admin` for base Compose, or to your organization's Directus URL. If a local override exposes Directus directly, `http://localhost:8055` may also be available.
2. Enter your email and password provided by your administrator.
3. You'll land on the Directus home screen.


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
2. If the optional Metabase profile is enabled, use its dashboards at the configured BI URL for visual analysis
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

This section covers how to enter each type of record through the Directus interface. Records are organized by category.

### Overview

| Category | Record types | Typical user |
|----------|-------------|--------------|
| **Farm Structure** | location, farm, plot, crop_cycle | Administrator, Manager |
| **Daily Operations** | farm_activity, harvest_event, expense_event, sales_event, loss_event, labor_event, field_note | Field Worker, Supervisor |
| **Environmental** | sensor_reading, weather_observation, weather_forecast | Analyst, Field Worker |
| **Certification & Stewardship** | organic_certification_record, land_stewardship_commitment | Manager, Administrator |
| **Stakeholder & Feedback** | stakeholder_feedback, impact_claim, metric_proposal | Any authenticated user |
| **Training & Emergency** | training_event, emergency_incident | Manager, Administrator |
| **Carbon & Credits** | carbon_credit, credit_retirement | Manager, Finance |
| **Data Stream** | data_stream_post, data_stream_post_comment | Any authenticated user |

### Farm Structure

These records define the geographic and operational hierarchy: **location → farm → plot → crop_cycle**.

#### Location

**Purpose:** Define a top-level geographic entity (e.g., a country or region).

1. Click **location** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **name** — Location name (e.g., "Kokonut Adelphi")
   - **country** — Country code
   - **latitude / longitude** — Coordinates
4. Click **Save**

#### Farm

**Purpose:** Define a named agricultural operation within a location.

1. Click **farm** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **name** — Farm name
   - **location_id** — Parent location
   - **latitude / longitude** — Farm coordinates
   - **area_hectares** — Total farm area
4. Click **Save**

#### Plot

**Purpose:** Define a specific cultivation area within a farm.

1. Click **plot** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **name** — Plot name (e.g., "North Field")
   - **farm_id** — Parent farm
   - **area_hectares** — Plot area
   - **bed_area_sqm** / **bed_count** — For per-square-meter yield models (optional)
   - **soil_type** — Dominant soil type
4. Click **Save**

#### Crop Cycle

**Purpose:** Track a single crop planting on a specific plot, from planting to harvest.

1. Click **crop_cycle** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **crop** — Crop type (maize, beans, cassava, coffee, avocado, tomato, banana, etc.)
   - **plot_id** — Parent plot
   - **planting_date** — When the crop was planted
   - **expected_harvest_date** — Estimated harvest date
   - **planting_density** — Plants per square meter (optional, activates per-m2 yield model)
   - **status** — active, completed, abandoned
4. Click **Save**

### Daily Operations

These are the records you enter most frequently.

#### Farm Activity

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

#### Harvest Event

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

#### Expense Event

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

#### Sales Event

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

#### Loss / Incident Event

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

#### Labor Event

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

#### Field Note

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

### Environmental

#### Sensor Reading

**Purpose:** Record a measurement from an IoT sensor (soil moisture, temperature, pH, etc.).

1. Click **sensor_reading** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **sensor_type** — soil_moisture, air_temperature, soil_ph, rainfall, wind_speed, etc.
   - **value** — Numeric measurement
   - **unit** — pct, celsius, mm, ph, etc.
   - **reading_date** — When the reading was taken
   - **device_id** — Which sensor device
   - **location_id** — Which location
4. Click **Save**

Readings can also be ingested automatically via MQTT or HTTP sensor push. See [Precision Agriculture](#10-precision-agriculture) for details.

#### Weather Observation

**Purpose:** Record historical weather data for a location.

1. Click **weather_observation** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **observation_date** — Date and time
   - **temperature_max / temperature_min** — Daily high/low
   - **rainfall_mm** — Precipitation
   - **humidity** — Relative humidity (%)
   - **wind_speed** — Wind speed
   - **solar_radiation** — Solar radiation (W/m2)
   - **location_id** — Which location
4. Click **Save**

### Certification & Stewardship

#### Organic Certification Record

**Purpose:** Track organic certification status for a location.

1. Click **organic_certification_record** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **certification_type** — organic, transitional, conventional
   - **certifying_body** — Who issued the certification
   - **certification_number** — Official number
   - **issue_date / expiry_date** — Validity period
   - **location_id** — Which location
4. Click **Save**

#### Land Stewardship Commitment

**Purpose:** Record a commitment to land stewardship practices.

1. Click **land_stewardship_commitment** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **commitment_type** — conservation, restoration, sustainable_management
   - **description** — What is being committed
   - **area_hectares** — Area covered
   - **start_date / end_date** — Commitment period
   - **location_id** — Which location
4. Click **Save**

### Stakeholder & Feedback

#### Stakeholder Feedback

**Purpose:** Capture structured feedback from workers, community members, buyers, and funders. Private by default; public exposure requires explicit consent.

1. Click **stakeholder_feedback** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **feedback_type** — complaint, suggestion, praise, concern, other
   - **category** — labor, environment, governance, financial, social, other
   - **content** — What was said
   - **stakeholder_type** — worker, community, buyer, funder, vendor, other
   - **consent_given** — Boolean (must be true for public exposure)
   - **public_summary** — Safe-for-public text (required if consent_given)
   - **location_id** — Which location
4. Click **Save**

**Important:** Feedback is private by default. A minimum 7-day review period applies before public exposure. See [Stakeholder & Governance](#14-stakeholder--governance) for the full workflow.

#### Impact Claim

**Purpose:** Make a structured impact claim with evidence maturity tracking.

1. Click **impact_claim** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **claim_type** — environmental, social, financial, governance
   - **title** — Short description
   - **evidence_maturity** — Level 0-6
   - **status** — proposed, discussed, approved, implemented, deprecated, rejected
   - **location_id** — Which location
4. Click **Save**

#### Metric Proposal

**Purpose:** Propose a new metric for the platform through participatory governance.

1. Click **metric_proposal** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **title** — Metric name
   - **description** — What it measures
   - **rationale** — Why it's needed
   - **proposed_by** — Who proposed it
   - **status** — proposed, discussed, approved, implemented, deprecated, rejected
   - **location_id** — Which location (or null for platform-wide)
4. Click **Save**

**Note:** Proposals require a minimum 30-day discussion period before approval.

### Training & Emergency

#### Training Event

**Purpose:** Record farmer training sessions and attendance.

1. Click **training_event** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **title** — Training topic
   - **training_date** — When it happened
   - ** trainer** — Who conducted it
   - **attendees_count** — How many people attended
   - **duration_hours** — How long
   - **topic** — soil_health, pest_management, financial_literacy, organic_practices, other
   - **location_id** — Which location
4. Click **Save**

#### Emergency Incident

**Purpose:** Record emergencies such as fires, floods, disease outbreaks, or equipment failures.

1. Click **emergency_incident** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **incident_type** — fire, flood, disease_outbreak, equipment_failure, chemical_spill, other
   - **incident_date** — When it happened
   - **severity** — low, medium, high, critical
   - **description** — What happened
   - **affected_area** — Area or plot affected
   - **response_action** — What was done
   - **location_id** — Which location
4. Click **Save**

### Data Stream

#### Data Stream Post

**Purpose:** Create a chronological monitoring post (photo, report, observation) that can be anchored on-chain.

1. Click **data_stream_post** in the left sidebar
2. Click **+** to create a new record
3. Fill in:
   - **post_type** — photo, monitoring_report, observation, other
   - **title** — Short summary
   - **content** — Detailed description
   - **location_id** — Which location
   - **status** — draft, submitted, verified, published, rejected
4. Click **Save**

Posts can be anchored on-chain via EAS for public verification. See [Data Governance & Identity](#15-data-governance--identity) for details.

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

### LLM Chat Assistant

The platform includes an optional AI chat interface for querying data using natural language. The assistant classifies your intent, extracts entities, and routes to structured query handlers.

**Usage (CLI):**

```bash
# Create a chat session
python3 -m services.analytics.llm_chat session --create --location-id <location-id> --user admin

# Send a message
python3 -m services.analytics.llm_chat chat --session-id <session-id> --message "What was the maize yield last month?"

# View chat history
python3 -m services.analytics.llm_chat history --session-id <session-id>

# List supported intents
python3 -m services.analytics.llm_chat intents
```

**Supported intents:** yield queries, weather data, soil conditions, CRISP scores, advisory recommendations, cost analysis, digital twin scenarios.

**Important:** The assistant returns structured data from governed records. It does not make decisions or modify data. All responses are read-only.

---

## 7. Viewing Dashboards

### Directus Dashboards

To access the Dashboard module:

1. Click the **Dashboard** icon in the left sidebar, or use your organization's Directus admin URL
2. Select the dashboard relevant to your role

**Available dashboards by role:**

| Role | Dashboard | What you see |
|------|-----------|-------------|
| Operator | Operations Overview | Active crop cycles, pending tasks, revenue, alerts, sensor data, weather, NDVI trend |
| Buyer | Buyer Dashboard | Production summary, upcoming harvests, quality grades, sales history, revenue trend |
| Funder | Funder Dashboard | Financial performance, NOI trend, cost breakdown, forecasts, impact attestations |
| Vendor | Vendor Dashboard | Purchase summary, history, demand forecast, payment status, category breakdown |

### Metabase Dashboards

Metabase is an optional BI service, not part of the default Compose stack. Enable it with `docker compose --profile metabase up -d metabase`; use the configured BI URL (locally, `http://localhost:3001`) and log in with your credentials.

The platform ships with **53 Metabase dashboards** organized by domain:

| Category | Dashboard | What it shows |
|----------|-----------|---------------|
| **Core Operations** | Farm Operations | Plot count, active crop cycles, total harvest, activity counts |
| | Crop NOI | Net Operating Income per crop cycle — revenue, direct costs, margin |
| | Expense Tracker | Expenses by category, direct vs shared costs, transaction counts |
| | Harvest & Sales | Monthly harvest volumes and sales revenue by crop with price trends |
| | Loss Rate | Loss analysis by crop and type — rate %, financial impact |
| | Eagle View | Platform-wide overview: stats, financials, harvest, revenue trend, attestations, sensors, environment |
| **Financial** | Financial Sustainability | Grant dependency, reinvestment, runway, risk mitigation |
| | Capital Efficiency | Scenario-based leverage, governance throughput, capital-provider utility |
| | Capital Alignment | Capital allocation alignment with regenerative goals |
| | Capital Provider Utility | Utility signals for capital providers |
| | Scaling Economics | Cost-per-farm economics, unit cost trends |
| | Scaling Roadmap | Milestones, dependencies, risk gates |
| | Green Paper Publication | Publication review status, evidence maturity |
| **Environmental** | Soil Carbon | Baseline vs latest soil organic carbon comparison |
| | Biodiversity | Shannon diversity index, habitat diversity |
| | NDVI Trends | Vegetation index time series |
| | Ecological Modeling | Trophic interactions, energy flow, population dynamics |
| | Trophic Pyramid | Energy flow across trophic levels |
| | Ecological Interactions | Species interaction web |
| | Resource Efficiency | Input-output ratios, water use efficiency |
| | Renewable Energy | Installed capacity, generation, carbon offset |
| **Impact Domains** | Holistic Well-being | Cultural context, community trust, operator capability |
| | Foundational Well-being | Basic needs, access, inclusion signals |
| | GNH Alignment | Domain-level well-being, cultural preservation |
| | Time Liberation | Labor time reclaimed through regenerative practices |
| | Cultural Preservation | Local knowledge, language, traditional practices |
| | Vulnerable Access | Access for vulnerable groups |
| | Regenerative Outcomes | Impact summaries, community governance, replication readiness |
| | Community Governance | Decision mechanisms, inclusion |
| | Land Stewardship | Commitment tracking, buffer compliance |
| | Adaptive Stewardship | Management loop effectiveness |
| | Replication Readiness | Checkpoint signals for farm replication |
| **Governance & Stakeholder** | Governance Throughput | Proposal-to-decision cycle times |
| | Governance Inclusion | Participation breadth and depth |
| | Anti-capture Governance | Policy compliance, redistribution status |
| | Participatory Governance | Community decision records |
| | Evidence Gap | Missing evidence by domain |
| | Stakeholder Feedback | Feedback volume, sentiment, resolution status |
| | Risk Mitigation | Risk register, mitigation status |
| **EBF & Scoring** | EBF Scorecard | Seven ecological benefit pillars with rubric bands |
| | Portfolio EBF | Cross-farm portfolio comparison |
| **Commons & Federation** | Redistribution Policy | Allocation scenarios and status |
| | Federation Mutual Aid | Cross-node data exchange health |
| | Algorithmic Redistribution | Automated redistribution status |
| | Participatory Signal | Advisory signal experiments |
| **Bio Factory** | Bio Factory Batches | Production batch status and yields |
| | Input Provenance | Ingredient sourcing and traceability |
| | Recipe Library | Available bio-factory recipes |
| | Quality Distribution | Quality test result distribution |
| | Regional Inputs | LAC regional input availability |
| **Pest & Organic** | Pest Management | Scouting activity, interventions, resistance alerts |
| | Livestock Feed Intake | Feed consumption and efficiency |
| | Token Reward Distribution | Reward distribution across participants |
| **Strategy & Planning** | Technology Roadmap | Technology adoption timeline |
| | DAO Proposal History | Governance proposal outcomes |

For details on building custom dashboards, see the [Partner Dashboards](partner-dashboards.md) guide.

### Accessing Dashboards

| Dashboard | URL | Login |
|-----------|-----|-------|
| Directus | `https://localhost/admin` or organization URL | Your Directus credentials |
| Metabase (opt-in) | `http://localhost:3001` locally after enabling the `metabase` profile, or organization URL | Your Metabase credentials |

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
# List available forecast scenarios
python3 -m services.forecast.cli --list

# Run all forecast scenarios for a location
python3 -m services.forecast.cli --location-id <location-id> --all

# Run or inspect a specific scenario
python3 -m services.forecast.cli --scenario-id <scenario-id>
python3 -m services.forecast.cli --scenario-id <scenario-id> --details

# Compare scenarios
python3 -m services.forecast.cli --compare <scenario-id-1> <scenario-id-2>

# Sensitivity analysis
python3 -m services.forecast.cli --scenario-id <scenario-id> --sensitivity --variable price
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

### CRISP Risk Scoring

The CRISP (Climate, Resilience, Implementation, Sustainability, Policy) risk engine scores locations across 5 dimensions with AAA-D rating bands.

```bash
# Composite risk rating
python3 -m services.crisp --composite --location-id <location-id> \
  --period-start 2026-01-01 --period-end 2026-06-30

# Individual risk dimensions
python3 -m services.crisp --carbon-yield --location-id <location-id>
python3 -m services.crisp --climate --location-id <location-id>
python3 -m services.crisp --policy --location-id <location-id>
python3 -m services.crisp --financial --location-id <location-id>
python3 -m services.crisp --implementation --location-id <location-id>

# Rate and persist
python3 -m services.crisp --rate --location-id <location-id> \
  --period-start 2026-01-01 --period-end 2026-06-30
```

**Rating bands:** AAA (0–<20), AA (20–<44), A (44–<69), B (69–<80), C (80–<91), D (91–100). Higher = more risk.

### SWOT & Strategy

```bash
# Create a SWOT analysis
python3 -m services.analytics.swot create --location-id <location-id> \
  --strengths "Strong soil" "Local market" --threats "Drought risk"

# Suggest factors from data
python3 -m services.analytics.swot suggest --location-id <location-id>

# Generate TOWS strategies
python3 -m services.analytics.swot tows generate --swot-id <swot-id>

# Business Model Canvas
python3 -m services.analytics.business_model_canvas create-from-data \
  --location-id <location-id>

# Pitch deck
python3 -m services.analytics.pitch generate --location-id <location-id> \
  --audience funders
```

### Revenue & Financial Analytics

```bash
# Revenue streams
python3 -m services.analytics.revenue_model create-stream \
  --location-id <location-id> --stream-name "Maize Sales" --stream-type crop_sales

# Break-even analysis
python3 -m services.analytics.revenue_model break-even \
  --location-id <location-id> --fixed-costs 10000 --variable-cost 2 --price 5

# Revenue forecast
python3 -m services.analytics.revenue_model forecast \
  --location-id <location-id> --periods 12
```

### Trend Analysis

```bash
# Trend estimation
python3 -m services.trends.estimator --metric-key soil_carbon_delta \
  --location-id <location-id>

# Mann-Kendall significance test
python3 -m services.trends.significance --test mann_kendall \
  --location-id <location-id>

# Change-point detection (CUSUM/PELT)
python3 -m services.trends.change_points --metric-key soil_carbon_delta \
  --location-id <location-id>

# ARIMA forecasting
python3 -m services.trends.forecasting --metric-key crop_revenue \
  --location-id <location-id> --horizon 30
```

### Geostatistics

```bash
# Variogram modeling
python3 -m services.geostatistics.cli variogram --location-id <location-id> \
  --property soil_carbon

# Ordinary kriging interpolation
python3 -m services.geostatistics.cli kriging --location-id <location-id> \
  --property soil_carbon --method ordinary --resolution 10

# Spatial autocorrelation (Moran's I)
python3 -m services.geostatistics.cli autocorrelation --location-id <location-id> \
  --property soil_carbon --weights queen
```

---

## 10. Precision Agriculture

### Weather Forecasts

```bash
# Ingest 5-day weather forecast for a location
python3 -m services.ingestion.weather_forecast --location-id <location-id>

# Get daily summary
python3 -c "from services.ingestion.weather_forecast import get_daily_summary, get_db; \
  print(get_daily_summary(get_db(), '<location-id>'))"

# Get spray windows (wind < 10 km/h, no rain)
python3 -c "from services.ingestion.weather_forecast import get_spray_windows, get_db; \
  print(get_spray_windows(get_db(), '<location-id>'))"
```

### Evapotranspiration & Water Balance

```bash
# Compute ET0 (Penman-Monteith)
python3 -m services.analytics.evapotranspiration et0 \
  --temp-max 30 --temp-min 18 --humidity 65 --wind 10 --solar 18 \
  --lat -1.2 --doy 180

# Field-level water balance
python3 -m services.analytics.evapotranspiration water-balance \
  --location-id <location-id>
```

### Crop Phenology (GDD)

```bash
# Accumulate Growing Degree Days
python3 -m services.analytics.crop_phenology accumulate --crop-cycle-id <id>

# Detect current growth stage
python3 -m services.analytics.crop_phenology detect-stage --crop-cycle-id <id>

# Project future stages
python3 -m services.analytics.crop_phenology project --crop-cycle-id <id>
```

### Prescription Maps (VRT)

```bash
# Classify application rates (natural breaks)
python3 -m services.analytics.prescription classify --crop maize --stage mid \
  --values 10,20,30,80,90,100

# Generate prescription map
python3 -m services.analytics.prescription generate \
  --location-id <location-id> --plot-id <plot-id> --input fertilizer

# Approve and estimate
python3 -m services.analytics.prescription approve --prescription-id <id> --approved-by admin
python3 -m services.analytics.prescription estimate --prescription-id <id>
```

### Advisory Engine

```bash
# Evaluate advisory rules for a location
python3 -m services.analytics.advisor evaluate --location-id <location-id>

# Run a full advisory cycle
python3 -m services.analytics.advisor run-cycle --location-id <location-id>

# List pending recommendations
python3 -m services.analytics.advisor pending --location-id <location-id>

# Accept or dismiss a recommendation
python3 -m services.analytics.advisor accept --recommendation-id <id> --user-id admin
python3 -m services.analytics.advisor dismiss --recommendation-id <id> --reason "not needed"
```

### Yield Monitoring

```bash
# Record a harvest yield
python3 -m services.analytics.yield_monitoring record \
  --location-id <location-id> --yield-amount 2500 --area 1.5 --crop maize

# Yield trend analysis
python3 -m services.analytics.yield_monitoring trend \
  --location-id <location-id> --crop maize

# Yield prediction (ensemble model)
python3 -m services.analytics.yield_monitoring predict \
  --location-id <location-id> --crop maize --days 60
```

### Precision Irrigation

```bash
# Create irrigation zone
python3 -m services.analytics.precision_irrigation create-zone \
  --location-id <location-id> --name "Zone A"

# Set soil moisture targets by crop stage
python3 -m services.analytics.precision_irrigation set-target \
  --zone-id <zone-id> --crop-stage vegetative \
  --target-min 50 --target-max 65 --trigger-pct 40 --refill-pct 65

# Generate irrigation schedule
python3 -m services.analytics.precision_irrigation schedule \
  --zone-id <zone-id> --etc 4.5 --rainfall 2.0 --moisture 42

# Water use efficiency report
python3 -m services.analytics.precision_irrigation water-efficiency \
  --location-id <location-id> --days 30
```

### Equipment & Digital Twin

```bash
# Equipment status
python3 -m services.analytics.equipment status --location-id <location-id>

# Equipment OEE (Availability x Performance x Quality)
python3 -m services.analytics.equipment oee --asset-id <asset-id>

# Create digital twin for simulation
python3 -m services.analytics.digital_twin create \
  --location-id <location-id> --name "Adelphi Twin"

# Run crop growth simulation
python3 -m services.analytics.digital_twin simulate --twin-id <twin-id>

# What-if scenario comparison
python3 -m services.analytics.digital_twin scenario \
  --twin-id <twin-id> --name "High Irrigation" \
  --params '{"irrigation_mm": 30}'
```

---

## 11. Pest Management

### Field Scouting & IPM

```bash
# Record a scouting observation
python3 -m services.analytics.pest_management record-scouting \
  --location-id <location-id> --pest fall_armyworm --type insect --severity moderate

# Set action thresholds (Economic Injury Level / Economic Threshold)
python3 -m services.analytics.pest_management set-threshold \
  --location-id <location-id> --pest fall_armyworm --crop maize --eil 2.0 --et 1.0

# Check if threshold is exceeded
python3 -m services.analytics.pest_management check-threshold \
  --location-id <location-id> --pest fall_armyworm --crop maize --count 3

# Record an intervention (IPM ladder: biological → cultural → mechanical → chemical)
python3 -m services.analytics.pest_management record-intervention \
  --location-id <location-id> --scouting-id <id> --type biological --method "Bt spray"
```

### Pesticide & Resistance Monitoring

```bash
# Log pesticide application
python3 -m services.analytics.pest_management record-pesticide \
  --location-id <location-id> --product "Bt spray" \
  --ingredient "Bacillus thuringiensis" --class bioinsecticide --rate 2.0 --area 1.0

# Monitor resistance development
python3 -m services.analytics.pest_management record-resistance \
  --location-id <location-id> --pest fall_armyworm --class pyrethroid --level moderate

# Degree-day tracking for lifecycle modeling
python3 -m services.analytics.pest_management record-degree-day \
  --location-id <location-id> --pest fall_armyworm --base 10.0 --max 38.0 --min 25.0
```

### Trap Monitoring & Spray Windows

```bash
# Add a monitoring trap
python3 -m services.analytics.pest_management add-trap \
  --location-id <location-id> --name "FAW Trap 1" --type pheromone --pest fall_armyworm

# Record trap catch
python3 -m services.analytics.pest_management record-catch --trap-id <id> --pest-count 15

# Check trap threshold
python3 -m services.analytics.pest_management check-trap-threshold --trap-id <id>

# Get spray windows (weather-based)
python3 -m services.analytics.pest_management spray-windows \
  --location-id <location-id> --pest fall_armyworm --days-ahead 7
```

---

## 12. Credit, Marketplace & Carbon

### Credit Classes & Batches

```bash
# Create a credit class
python3 -m services.credit_class.cli class create \
  --name "Kokonut Carbon" --methodology "IPCC 2006" --type carbon

# Create a credit batch
python3 -m services.credit_class.cli batch create \
  --class-id <id> --location-id <location-id> --vintage 2026 --quantity 100

# Issue credits
python3 -m services.credit_class.cli batch issue --batch-id <id> --issuer 0x1234

# Check balance
python3 -m services.credit_class.cli batch balance --batch-id <id>
```

### Marketplace

```bash
# List credits for sale
python3 -m services.credit_class.cli marketplace sell \
  --batch-id <id> --seller 0x1234 --quantity 100 --price 2500 --denom cusd

# Buy credits
python3 -m services.credit_class.cli marketplace buy \
  --sell-order-id <id> --buyer 0x5678 --quantity 50

# Execute trade
python3 -m services.credit_class.cli marketplace execute --buy-order-id <id>
```

### Carbon Credit Lifecycle

```bash
# Issue carbon credits
python3 -m services.analytics.carbon_credits --issue \
  --location-id <location-id> --vintage-year 2026 --methodology "IPCC 2006 Tier 2"

# Retire credits (with human confirmation)
python3 -m services.analytics.carbon_credits --retire \
  --credit-id <id> --tonnes 5.0 --reason voluntary_retirement

# Check balance
python3 -m services.analytics.carbon_credits --balance --location-id <location-id>
```

### Data Stream & Anchoring

```bash
# Post a monitoring report
python3 -m services.data_stream.cli post --location-id <location-id> \
  --type monitoring_report --title "Monthly Soil Report" --content "..."

# Anchor on-chain via EAS
python3 -m services.data_stream.cli anchor --post-id <id> --chain celo

# Full-text search across posts
python3 -m services.data_stream.cli search --query "soil moisture" --location-id <id>
```

---

## 13. Cooperative & Digital Finance

### Cooperative Management

```bash
# Create a cooperative
python3 -m services.analytics.cooperative create-coop \
  --name "Adelphi Coop" --type marketing --location-id <location-id> \
  --governance one_member_one_vote

# Add members
python3 -m services.analytics.cooperative add-member \
  --cooperative-id <id> --farmer-id <farmer-id> --role member --shares 10

# Book shared equipment
python3 -m services.analytics.cooperative book-asset \
  --asset-id <id> --membership-id <id> \
  --start "2026-07-15T08:00" --end "2026-07-20T17:00"

# Collective bulk purchasing
python3 -m services.analytics.cooperative create-purchase \
  --cooperative-id <id> --order-name "Bulk Seeds" --category seeds \
  --target-qty 1000 --unit kg --target-price 2.50
```

### Digital Finance

```bash
# Create a savings account
python3 -m services.analytics.digital_finance create-account \
  --location-id <location-id> --type savings --currency KES --holder "John Doe"

# Create weather-index insurance
python3 -m services.analytics.digital_finance create-insurance \
  --location-id <location-id> --product weather_index \
  --coverage 100000 --premium 5000

# File an insurance claim
python3 -m services.analytics.digital_finance file-claim \
  --policy-id <id> --type drought --amount 20000 \
  --evidence '{"rainfall_deficit": 40}'

# Create a loan
python3 -m services.analytics.digital_finance create-loan \
  --location-id <location-id> --amount 50000 --rate 0.12 --term 12 \
  --purpose "input_purchase" --eligibility 0.85
```

### Traceability

```bash
# Create a traceability batch
python3 -m services.analytics.traceability create-batch \
  --location-id <location-id> --crop maize --quantity 500 --harvest-date 2026-07-10

# Record custody transfer
python3 -m services.analytics.traceability custody \
  --batch-id <id> --from "Farm A" --to "Cooperative B" --type harvest_collection

# Quality check
python3 -m services.analytics.traceability quality \
  --batch-id <id> --type visual --result pass --grade A

# Full provenance trace
python3 -m services.analytics.traceability provenance-log --batch-id <id>
```

---

## 14. Stakeholder & Governance

### Stakeholder Engagement

```bash
# Create an engagement plan
python3 -m services.analytics.cli_stakeholder_engagement create-plan \
  "Community Consultation Plan" --stakeholder-party-id <party-id>

# Schedule a touchpoint
python3 -m services.analytics.cli_stakeholder_engagement schedule-touchpoint \
  <plan-id> "Quarterly review" --channel-type sms --consent-checked

# Check commitment health
python3 -m services.analytics.cli_stakeholder_engagement commitment-health
```

### Stakeholder Trust & Decisions

```bash
# Record trust evidence
python3 -m services.analytics.cli_stakeholder_trust record-evidence \
  <party-id> payment supporting financial_transaction \
  "Payment settled within agreed terms" --confidence 0.9

# Create a governed decision
python3 -m services.analytics.cli_stakeholder_decisions create \
  "Irrigation Upgrade" "Expand drip system to North Field" policy \
  --created-by-party-id <party-id>

# Add trade-off analysis
python3 -m services.analytics.cli_stakeholder_decisions add-tradeoff \
  <decision-id> harm "Potential water access impact" --severity 8 \
  --mitigation "Protect minimum access"
```

### Governance Framework (Baal/Moloch)

```bash
# List configured governance frameworks
python3 -m services.governance.cli framework list

# View Baal governance config
python3 -m services.governance.cli baal config

# List proposals
python3 -m services.governance.cli baal proposals

# View member state
python3 -m services.governance.cli baal member 0xWALLET
```

---

## 15. Data Governance & Identity

### Consent & Access Control

```bash
# Record data consent
python3 -m services.analytics.data_governance record-consent \
  --farmer-id F001 --data-category soil --scope collection --status granted

# Check consent before accessing data
python3 -m services.analytics.data_governance check-consent \
  --farmer-id F001 --data-category soil --scope collection

# Log data access for audit
python3 -m services.analytics.data_governance log-access \
  --accessor-id A001 --data-category soil --resource-type soil_sample --access-type read

# Request data portability (GDPR-style)
python3 -m services.analytics.data_governance request-portability \
  --farmer-id F001 --format csv --scope all
```

### Farmer Identity & KYC

```bash
# Create a farmer profile
python3 -m services.analytics.farmer_identity create-profile \
  --first-name John --location-id <location-id>

# Add credentials (organic cert, training cert, etc.)
python3 -m services.analytics.farmer_identity add-credential \
  --farmer-id <id> --type organic_cert --name "Organic Certificate"

# Create KYC record
python3 -m services.analytics.farmer_identity create-kyc \
  --farmer-id <id> --method national_id
```

### Extension & Training

```bash
# Create a training module
python3 -m services.analytics.extension create-module \
  --title "Soil Health 101" --category soil_health --content-type guide

# Enroll a farmer
python3 -m services.analytics.extension enroll \
  --farmer-id <farmer-id> --module-id <module-id>

# Track delivery (SMS, WhatsApp, in-person)
python3 -m services.analytics.extension deliver \
  --farmer-id <farmer-id> --module-id <module-id> --channel sms
```

---

## 16. Exporting Data

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

The platform generates **87 report types** as governed snapshots with SHA-256 hashes. Reports are organized by domain:

```bash
# List all available report types
python3 -m services.export.report_generator --list

# Generate a specific report
python3 -m services.export.report_generator --type farm_summary --location-id <location-id>

# Auto-generate all report types for a location
python3 -m services.export.report_generator --auto --location-id <location-id>
```

**Most-used report types by category:**

| Category | Report types |
|----------|-------------|
| **Core** | `farm_summary`, `crop_noi`, `environmental`, `comprehensive_status` |
| **Financial** | `financial_sustainability`, `capital_efficiency`, `scaling_economics`, `revenue_streams` |
| **Ecological** | `climate_impact`, `ecological_modeling`, `resource_efficiency` |
| **Impact Domains** | `holistic_wellbeing`, `foundational_wellbeing`, `gnh_alignment`, `regenerative_outcomes`, `open_source_impact` |
| **Governance** | `governance_throughput`, `anti_capture_governance`, `participatory_governance`, `federation_mutual_aid` |
| **Stakeholder** | `stakeholder_landscape`, `stakeholder_engagement`, `stakeholder_trust`, `stakeholder_cockpit` |
| **EBF & CRISP** | `ebf_scorecard`, `risk_mitigation` |
| **Strategy** | `pitch_deck`, `business_model_canvas`, `capability_dashboard`, `strategy_execution` |
| **Operational** | `pest_management`, `data_stream_summary`, `training_impact` |
| **Credit & Carbon** | `bio_factory_batch`, `organic_certification_readiness` |
| **Composite** | `state_of_kokonut` (ecosystem-wide), `tactical_layer`, `simulation_wargame` |

See the [Export Guide](export-guide.md) for the full list of 87 report types and their schemas.

### CIDS Export

```bash
# Export location data as CIDS v3.2.0 JSON-LD
python3 -m services.registry.cids_export --location-id <location-id>
```

Reports are stored as snapshots with SHA-256 hashes for verification.

---

## 17. Working with the SDK

### Python SDK

```bash
cd sdk/python && pip install -e .
```

**Quick start:**

```python
from kokonut import KokonutClient

client = KokonutClient("https://localhost/directus", "your-api-token")

# List farms
farms = client.farms.list()

# Create a harvest event
harvest = client.harvest_events.create({
    "harvest_date": "2026-06-15",
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

**Available method classes:**

| Class | Description |
|-------|-------------|
| `client.locations` | Location CRUD and queries |
| `client.farms` | Farm management |
| `client.plots` | Plot definitions and queries |
| `client.crop_cycles` | Crop cycle lifecycle |
| `client.harvest_events` | Harvest recording and queries |
| `client.sales_events` | Sales recording and queries |
| `client.expense_events` | Expense recording and queries |
| `client.sensor_readings` | Sensor data ingestion |
| `client.wallet_profiles` | Web3 wallet profiles |
| `client.attestations` | EAS attestation management |
| `client.reports` | Report generation and snapshots |
| `client.exports` | Data export (CSV, JSON, Parquet) |

**Error types:**

| Error | Meaning |
|-------|---------|
| `AuthenticationError` | Invalid or missing API token |
| `NotFoundError` | Record or collection does not exist |
| `PermissionError` | Your role lacks access to this resource |
| `ValidationError` | Input data failed validation rules |

See `sdk/python/examples/` for full examples including workflow lifecycle, batch uploads, and NOI queries.

### JavaScript/TypeScript SDK

```bash
cd sdk/javascript && npm install && npm run build
```

**Quick start:**

```typescript
import { KokonutClient } from '@kokonut/intelligence';

const client = new KokonutClient('https://localhost/directus', 'your-api-token');

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

## 18. Understanding Attestations

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

## 19. Linked Data & Querying

### IRI System

Every governed entity gets a deterministic **Internationalized Resource Identifier** in the format `kokonut:{entity_type}:{entity_id}:v{version}`. IRIs provide stable, versioned references across the platform.

```bash
# Generate an IRI for a location
python3 -m services.iri.cli generate --entity-type location --entity-id <id>

# Resolve an IRI to its metadata
python3 -m services.iri.cli resolve --iri "kokonut:location:<id>:v1"

# View IRI history (all versions)
python3 -m services.iri.cli history --entity-type location --entity-id <id>

# Anchor an IRI on-chain
python3 -m services.iri.cli anchor --iri "kokonut:location:<id>:v1" --chain celo
```

### RDF Triple Store

Governed records are projected into an RDF triple store for linked-data queries. Triples are built from the canonical PostgreSQL schema and stored in named graphs per location.

```bash
# Build RDF triples for a location
python3 -m services.rdf.cli build --location-id <location-id>

# Query triples by subject
python3 -m services.rdf.cli query --subject "kokonut:location:<id>"

# Count triples in a graph
python3 -m services.rdf.cli count --graph "location:adelphi"

# Serialize as Turtle
python3 -m services.rdf.cli serialize --format turtle --graph "location:adelphi"
```

### Metadata Graph API

The platform serves JSON-LD metadata at a REST endpoint for external consumers.

```bash
# Resolve full ProjectInfo via IRI
python3 -m services.metadata_api.cli resolve --iri "kokonut:location:<id>:v1"

# Generate metadata from a JSON document
python3 -m services.metadata_api.cli generate --metadata '{"@type":"location","name":"Test"}'

# Start the metadata API server
python3 -m services.metadata_api.cli serve --port 8099
```

---

## 20. Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Can't log in | Check with your administrator that your account is active and your role is assigned |
| Can't see a collection | Your role may not have access. Ask your administrator. |
| Can't edit a record | The record may not be in **draft** status, or it may not belong to your location |
| Can't submit a record | You may not have permission. Ask a Supervisor to submit it for you. |
| Can't verify a record | Only Managers and Finance can verify. Check your role. |
| Expense category looks wrong | The auto-categorization is keyword-based. Manually override the category if needed. |
| Metabase dashboards not loading | Start the optional service with `docker compose --profile metabase up -d metabase`, then check `docker compose ps` |
| Directus not accessible | Ensure Directus is running: `docker compose ps` |
| Export fails | Check that the collection name is valid and you have read access |
| Attestation fails | Verify your private key is in `.env` and the chain is accessible |
| CRISP score seems wrong | Check that source data (harvest, weather, soil) is populated; CRISP queries existing records |
| Weather forecast not showing | Run `python3 -m services.ingestion.weather_forecast --location-id <id>` to ingest |
| Sensor readings not appearing | Verify MQTT/HTTP sensor push is configured; check `device_manager --health` |
| Advisory recommendations empty | Run `python3 -m services.analytics.advisor evaluate --location-id <id>` to trigger evaluation |
| Chat assistant returns errors | Ensure the session is created first with `llm_chat session --create` |
| Trade/order status stuck | Check the governed lifecycle; records require human review at each transition |
| Data stream post not anchoring | Verify EAS chain is accessible; check attestation CLI with `info --chain celo` |

### Getting Help

| Topic | Document |
|-------|----------|
| System overview | [Architecture Guide](architecture.md) |
| API endpoints | [API Reference](api-reference.md) |
| Field definitions | [Data Dictionary](data-dictionary.md) |
| EAS setup | [Attestation Guide](attestation-guide.md) |
| Export details | [Export Guide](export-guide.md) |
| Daily operations | [Operator Guide](operator-guide.md) |
| Field data collection | [Field Data Collection Guide](field-data-collection-guide.md) |
| Review workflow | [Reviewer Guide](reviewer-guide.md) |
| Partner dashboards | [Partner Dashboards](partner-dashboards.md) |
| Full platform description | [Green Paper](green-paper.md) |

---

## 21. Glossary

| Term | Definition |
|------|-----------|
| **Attestation** | A verifiable claim published on-chain (EAS) or signed off-chain (EIP-712) |
| **Baal** | The Moloch v3 governance framework used by Kokonut DAO on Gnosis Chain |
| **CRISP** | Climate, Resilience, Implementation, Sustainability, Policy — 5-dimension risk scoring engine with AAA-D rating bands |
| **Crop cycle** | The lifecycle of a single crop planting on a specific plot, from planting to harvest |
| **CIDS** | Common Impact Data Standard — a JSON-LD interoperability format for impact data |
| **CUSUM/PELT** | Change-point detection algorithms used in trend analysis |
| **Delphi** | Roundless expert consultation method with pseudonymous panels and consensus tracking |
| **Directus** | The admin UI and API layer for managing the PostgreSQL database |
| **Draft** | Initial status of a record — being created or edited |
| **EAS** | Ethereum Attestation Service — a protocol for on-chain attestations on Celo |
| **EBF** | Ecological Benefit Framework — 7-pillar scorecard for regenerative impact assessment |
| **EIL/ET** | Economic Injury Level / Economic Threshold — IPM action trigger points |
| **ET0** | Reference evapotranspiration (Penman-Monteith equation) |
| **Farm** | A named agricultural operation containing one or more plots |
| **Fortune 500** | The platform's farm scoring system (0–1000 scale across 4 pillars) |
| **GDD** | Growing Degree Days — heat-unit accumulation for crop phenology tracking |
| **IRI** | Internationalized Resource Identifier — deterministic `kokonut:{type}:{id}:v{version}` identifiers for governed entities |
| **KokonutResolver** | Smart contract that gates who can create attestations on the platform |
| **Lifecycle** | The 4-stage status flow: draft → submitted → verified → published |
| **Location** | The top-level geographic entity (e.g., a country or region) |
| **MRV** | Measurement, Reporting, and Verification — the process of collecting and validating environmental data |
| **NOI** | Net Operating Income — revenue minus direct costs minus allocated shared costs |
| **NOI snapshot** | Periodic financial summary recording NOI, revenue, and cost breakdown |
| **Offchain attestation** | A signed claim stored off-chain, verifiable without blockchain gas fees |
| **Onchain attestation** | A claim published to the Celo blockchain, publicly verifiable |
| **Operating margin** | NOI as a percentage of net revenue |
| **OODA** | Observe, Orient, Decide, Act — the platform's decision-making loop architecture |
| **Plot** | A specific cultivation area within a farm, with defined boundaries |
| **Published** | Final status — record is available to dashboards and reports |
| **RDF** | Resource Description Framework — triple-store format for linked data |
| **Rejected** | Status indicating a record needs correction, with a reason provided |
| **Row-level security** | Access control that limits which rows a user can see based on their role and assignments |
| **Schema** | The database structure defining tables, columns, and relationships |
| **SPARQL** | Query language for RDF triple stores |
| **Submitted** | Status indicating a record is ready for review |
| **Threatcasting** | Forward-looking threat identification with cross-impact analysis, warning flags, and backcasting |
| **Verified** | Status indicating a record has been reviewed and approved |
| **VRT** | Variable Rate Technology — prescription maps for site-specific input application |
| **Workflow history** | Audit log of every status change on a record |
