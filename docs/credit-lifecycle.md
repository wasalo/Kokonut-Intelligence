# Credit Lifecycle

The credit system spans class definition, batch issuance, per-account custody, marketplace trading, cross-chain bridging, basket tokenization, and human-reviewed retirement. Two parallel representations coexist: the **ecocredit hierarchy** (credit class → batch → balance) and the **legacy carbon credit identity** (per-`078_carbon_credits.sql`). Both are governed; agents may draft but never publish or retire.

## Hierarchy

```text
credit_type (carbon | biodiversity | water | soil | mixed)
  └── credit_class (methodology definition, status lifecycle)
        ├── credit_class_cobenefit
        ├── credit_class_registry
        ├── crediting_program
        ├── credit_protocol
        ├── credit_class_methodology
        ├── buffer_pool_account
        ├── credit_class_issuer (authorized minters)
        └── credit_batch (issuance event, status lifecycle)
              ├── credit_batch_contract (on-chain link)
              ├── credit_balance (per-account: tradable / retired / escrowed)
              ├── credit_basket_deposit (pooled in basket)
              └── credit_sell_order (marketplace listing)

credit_basket (fungible token pool)
  ├── credit_basket_deposit
  └── credit_basket_token (holder balances)

credit_sell_order → credit_buy_order (marketplace fill)
marketplace_fee → marketplace_fee_distribution (fee trail)

credit_bridge_transaction (cross-chain movement)
project_credit_class_enrollment (project → class enrollment)
carbon_credit (legacy individual identity, per-078)
```

## Credit Types

`credit_type` defines the unit of measurement for all credits under a class.

| Type | Abbreviation | Unit | Description |
|------|-------------|------|-------------|
| carbon | C | tonneCO2e | Carbon sequestration or avoidance |
| biodiversity | B | species_ha | Biodiversity uplift |
| water | W | m3 | Water saved or restored |
| soil | S | tonne | Soil carbon or organic matter |
| mixed | M | unit | Composite or multi-benefit |

```bash
python3 -m services.credit_class.cli credit-type list
```

Types are seeded at deployment; the abbreviation drives basket token denomination (see [Basket](#basket-fungible-token-pool)).

## Credit Classes

A `credit_class` defines the methodology, governance, and eligibility rules for a family of credits.

```bash
python3 -m services.credit_class.cli class create \
  --name "Kokonut Carbon" --methodology "IPCC 2006" \
  --type carbon --url https://example.com

python3 -m services.credit_class.cli class get --class-id UUID
python3 -m services.credit_class.cli class list --type carbon --status published
```

### Key Fields

| Column | Description |
|--------|-------------|
| `name` | Human-readable class name |
| `methodology` | Methodology identifier (e.g. IPCC 2006) |
| `credit_type` | One of the five credit types |
| `ecosystem_types` | Applicable ecosystem categories |
| `eligible_activities` | Allowed sequestration activities |
| `crediting_period_years` | Default crediting period (default: 10) |
| `registry_slug` | External registry identifier |
| `chain` | Target chain (default: celo) |
| `allowlist_required` | If true, creators must be allowlisted |
| `approval_required` | If true, batches require approval before issuance |

### Status Lifecycle

```text
draft → submitted → verified → published → deprecated
                 ↘ rejected
```

Agents may set `draft`, `submitted`, or `rejected`. Only humans may set `verified` or `published`.

### Child Entities

Each credit class can have associated metadata:

- **Cobenefits** — secondary impacts (e.g. biodiversity, water quality) with SDG links
- **Registries** — external registry links (e.g. Verra VCS, Gold Standard)
- **Programs** — crediting programs the class participates in
- **Protocols** — measurement protocols (primary or secondary)
- **Methodologies** — approved calculation methodologies
- **Buffer pools** — insurance pool accounts with wallet addresses

```bash
python3 -m services.credit_class.cli cobenefit add \
  --credit-class-id UUID --impact-name "Biodiversity" \
  --impact-type biodiversity --sdg-numbers 14 15

python3 -m services.credit_class.cli registry add \
  --credit-class-id UUID --registry-name "Verra"

python3 -m services.credit_class.cli protocol add \
  --credit-class-id UUID --name "IPCC 2006 Tier 2" --is-primary

python3 -m services.credit_class.cli methodology add \
  --credit-class-id UUID --name "VM0042" --is-approved

python3 -m services.credit_class.cli buffer-pool add \
  --credit-class-id UUID --name "Kokonut Pool" \
  --wallet-address 0x1234
```

### Issuer Authorization

Only addresses registered via `credit_class_issuer` may mint batches. Revocation is tracked via `revoked_at`; a non-null `revoked_at` means the issuer is no longer authorized.

```bash
python3 -m services.credit_class.cli issuer add \
  --class-id UUID --address 0x1234 --name "Kokonut DAO"
python3 -m services.credit_class.cli issuer list --class-id UUID
```

### Allowlist

When `allowlist_required = TRUE`, only addresses in `credit_class_creator_allowlist` may create classes of that type.

```bash
python3 -m services.credit_class.cli allowlist add \
  --address 0x1234 --name "Kokonut"
python3 -m services.credit_class.cli allowlist list
```

## Enrollment

A project (location) enrolls in a credit class before issuing batches. Enrollment tracks the application lifecycle between the project and the class administrator.

```bash
python3 -m services.credit_class.cli enrollment apply \
  --location-id UUID --class-id UUID
python3 -m services.credit_class.cli enrollment evaluate \
  --enrollment-id UUID --issuer 0x1234 --status accepted
python3 -m services.credit_class.cli enrollment list-by-class --class-id UUID
python3 -m services.credit_class.cli enrollment list-by-project --location-id UUID
```

### State Diagram

```text
applied ──────→ changes_requested ──→ accepted ──→ terminated
   │                   │                  │
   └──────────────────→│                  │
   │                   └──────────────────→│
   └──────────────────→ rejected
```

| Transition | Valid From |
|-----------|-----------|
| `changes_requested`, `accepted`, `rejected` | `applied` |
| `changes_requested`, `accepted`, `rejected` | `changes_requested` |
| `terminated` | `accepted` |
| (terminal) | `rejected`, `terminated` |

Re-applying when an enrollment already exists in `rejected`, `terminated`, or `accepted` status creates a new lifecycle from `applied`. Uniqueness is enforced per `(location_id, credit_class_id)`.

## Batches

A `credit_batch` represents a single issuance event within a class. Batch codes are auto-generated from class abbreviation, location abbreviation, and vintage year.

```bash
python3 -m services.credit_class.cli batch create \
  --class-id UUID --location-id UUID --vintage 2026 --quantity 100

python3 -m services.credit_class.cli batch list --class-id UUID
python3 -m services.credit_class.cli batch get --batch-id UUID
```

### Key Fields

| Column | Description |
|--------|-------------|
| `batch_code` | Auto-generated unique code (e.g. `CC-IPV-2026-ADEL-0001`) |
| `total_quantity` | Total credits in the batch |
| `issued_quantity` | Credits issued to date |
| `retired_quantity` | Credits permanently retired |
| `cancelled_quantity` | Credits cancelled |
| `available_quantity` | Computed: `issued - retired - cancelled` |
| `evidence_maturity` | Evidence maturity level (1–6) |
| `is_open` | If true, batch accepts additional issuance |
| `jurisdiction` | Regulatory jurisdiction |
| `origin_tx_*` | On-chain origin transaction provenance |

### Status Lifecycle

```text
draft → submitted → verified → published → retired
                                    ↘ cancelled
                 ↘ rejected
```

### Batch Contract Link

`credit_batch_contract` records the on-chain token contract for a batch on each chain. Uniqueness is enforced per `(credit_batch_id, chain)`.

## Issuance

Issuance converts a verified batch into published credits and mints the issuer's balance.

```bash
python3 -m services.credit_class.cli batch issue \
  --batch-id UUID --issuer 0x1234
```

### Flow

1. Validate batch status is `verified`.
2. Validate the issuer address is authorized (non-revoked entry in `credit_class_issuer`).
3. Set batch status to `published`.
4. Credit the issuer's `credit_balance.tradable_amount` with `total_quantity`.
5. Record `minted_at` timestamp.

A batch may be issued multiple times if `is_open = TRUE`, crediting additional quantity to the issuer each time.

## Balances

`credit_balance` is the per-account custody ledger. Three compartments track how credits are held:

| Compartment | Description |
|-------------|-------------|
| `tradable_amount` | Available for sale, transfer, or escrow |
| `escrowed_amount` | Locked by an active marketplace sell order |
| `retired_amount` | Permanently retired; cannot be reactivated |

```bash
python3 -m services.credit_class.cli balance get \
  --batch-id UUID --account 0x1234
python3 -m services.credit_class.cli balance account --account 0x1234
python3 -m services.credit_class.cli balance batch --batch-id UUID
python3 -m services.credit_class.cli balance all
python3 -m services.credit_class.cli balance supply --batch-id UUID
```

### Non-Negative Enforcement

`upsert_balance` applies delta values (positive or negative) to each compartment atomically. A `WHERE` clause ensures no compartment drops below zero. If the update affects zero rows, the operation raises `"Insufficient balance"` and rolls back.

### Public Views

- **`v_public_carbon_credit_inventory`** — published carbon credits with evidence_maturity=6 and a verified/published `farm_registry_record`
- **`v_carbon_credit_balance`** — aggregated balance per location (total_issuable, total_retired, total_reserved, total_available, published_count, retired_count)

Both views require a verified or published `farm_registry_record` for the location.

## Carbon Credits (Legacy Identity)

`carbon_credit` is the legacy per-credit identity table from `078_carbon_credits.sql`. It tracks individual credit codes, sequestration quantities, pricing, and attestation metadata. The ecocredit hierarchy (class → batch → balance) is the preferred representation for new issuances; `carbon_credit` remains for backward compatibility and the governed retirement flow.

### Key Fields

| Column | Description |
|--------|-------------|
| `credit_code` | Unique code (e.g. `KKNT-2026-ADELPHI-0001`) |
| `initial_sequestration_tonnes` | Original sequestration estimate |
| `current_sequestration_tonnes` | Adjusted sequestration (after corrections) |
| `issuable_tonnes` | Total issuable after margins |
| `reserved_tonnes` | Temporarily locked by pending retirement |
| `retired_tonnes` | Permanently retired |
| `available_tonnes` | Computed: `issuable - retired - reserved` |
| `adjustment_margin_pct` | Max allowable adjustment without review (0–50%) |
| `buffer_pool_pct` | Retained in buffer pool (0–50%) |
| `evidence_maturity` | Must be 6 for published status |
| `external_verifier` | Required for published status |
| `methodology_ref` | Required for published status |

### Status Lifecycle

```text
draft → submitted → verified → published → retired
                                    ↘ revoked
                 ↘ rejected
```

### Published Constraint

Status `published` requires all of:
- `evidence_maturity = 6`
- `external_verifier IS NOT NULL` and non-empty
- `methodology_ref IS NOT NULL` and non-empty

This is enforced by the `chk_carbon_credit_public_level6` database check.

### Public Inventory

`v_public_carbon_credit_inventory` exposes only published credits where `evidence_maturity = 6` and the location has a verified or published `farm_registry_record`.

## Adjustments

`credit_adjustment` records corrections to a carbon credit's sequestration quantity. Each adjustment tracks the trigger, the delta, and whether human review is required.

```bash
python3 -m services.analytics.carbon_credits --adjust --location-id UUID
```

### Adjustment Types

| Type | Description |
|------|-------------|
| `measurement_update` | New field measurement changes the estimate |
| `methodology_change` | Calculation methodology was updated |
| `reversal` | Sequestration loss detected |
| `correction` | Error correction in prior calculation |

### Trigger Sources

| Source | Description |
|--------|-------------|
| `tree_inventory` | Tree count or biomass update |
| `soil_carbon_measurement` | Soil sample analysis |
| `ghg_emissions_inventory` | Greenhouse gas audit |
| `climate_impact_summary` | Climate impact reassessment |
| `remote_sensing` | Satellite or drone analysis |
| `manual_override` | Operator-initiated correction |

### Review Flags

- `within_margin` — TRUE if delta is within the class's `adjustment_margin_pct`
- `requires_review` — TRUE if the adjustment exceeds the margin or is a reversal

Adjustments within margin may proceed without human review; those outside margin or flagged as reversals require reviewer approval.

## Marketplace Escrow

The marketplace enables peer-to-peer credit trading with atomic escrow.

### Sell Order

```bash
python3 -m services.credit_class.cli marketplace sell \
  --batch-id UUID --seller 0x1234 --quantity 50 \
  --price 2500 --denom cusd
```

1. Validate `ask_denom` is in `credit_allowed_denom` (active).
2. Atomically decrement seller's `tradable_amount`, increment `escrowed_amount`.
3. Insert `credit_sell_order` with `escrow_quantity = quantity`, status `active`.

### Buy Order

```bash
python3 -m services.credit_class.cli marketplace buy \
  --sell-order-id UUID --buyer 0x5678 --quantity 25
```

1. Validate sell order is active with sufficient escrow.
2. Compute `total_price = (buy_qty / sell_qty) × ask_price`.
3. Compute buyer fee; reject if fee exceeds `max_fee_amount`.
4. Enforce auto-retire constraints (buyer cannot disable if seller requires it).
5. Insert `credit_buy_order` with status `pending`.

### Execution

```bash
python3 -m services.credit_class.cli marketplace execute --buy-order-id UUID
```

1. Lock both orders (`FOR UPDATE`).
2. Validate sell order still has sufficient escrow.
3. Decrement seller's `escrowed_amount`.
4. **If auto_retire:** Credit buyer's `retired_amount`; increment `credit_batch.retired_quantity`.
5. **If not auto_retire:** Credit buyer's `tradable_amount`.
6. Update sell order: decrement `escrow_quantity`; if zero, set status `filled`.
7. Set buy order status `completed`.

### Cancellation and Expiration

- **Cancel:** Seller calls cancel; escrow returns to `tradable_amount`; status set `cancelled`.
- **Expire:** `expire_sell_orders` sweeps all active orders where `expiration < NOW()`; returns escrow to seller; status set `expired`.

### Price Calculation

```
total_price = (quantity / sell_order.quantity) × sell_order.ask_price
```

This is a proportional split, not a per-unit multiplication. Partial fills reduce the sell order's escrow proportionally.

### Allowed Denominations

`credit_allowed_denom` stores active trading denominations. Seeded values: `uusd` (celo), `cusd` (celo), `ceur` (celo).

```bash
python3 -m services.credit_class.cli marketplace denoms
```

## Fees

Marketplace fees are configurable via `ecocredit_params` and collected separately from the trade execution.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `marketplace_buyer_fee` | `0.03` (3%) | Fee rate on buyer side |
| `marketplace_seller_fee` | `0.03` (3%) | Fee rate on seller side |
| `marketplace_fee_pool_address` | null | Recipient address for fee pool |

### Collection Flow

1. `collect_fee` records a `marketplace_fee` row with `status = pending`, capturing buyer_fee, seller_fee, total, and fee_denom.
2. `distribute_fee` creates a `marketplace_fee_distribution` row and updates the fee status to `distributed`.

Fees are **not** automatically deducted during `execute_buy_order`. Collection and distribution are separate steps.

```bash
python3 -m services.credit_class.cli params get --key marketplace_buyer_fee
python3 -m services.credit_class.cli params get --key marketplace_seller_fee
```

## Basket (Fungible Token Pool)

A basket pools heterogeneous credit batches into a fungible basket token. Deposits of non-fungible batches mint basket tokens; withdrawals burn tokens and return credits in FIFO order.

```bash
python3 -m services.credit_class.cli basket create \
  --name "Carbon Basket" --denom cusd
python3 -m services.credit_class.cli basket deposit \
  --basket-id UUID --batch-id UUID --address 0x1234 \
  --quantity 100 --token-amount 100000000
python3 -m services.credit_class.cli basket balance \
  --basket-id UUID --address 0x1234
```

### Token Denomination

```
token_denom = "eco.{SI_PREFIX}{credit_type_abbrev}.{basket_name}"
```

| Exponent | SI Prefix | Example |
|----------|-----------|---------|
| 0 | (none) | `eco.C.Carbon Basket` |
| 6 | u | `eco.uC.Carbon Basket` |
| 9 | n | `eco.nC.Carbon Basket` |

Token amount formula: `token_amount = quantity × 10^exponent` (default exponent: 6).

### Deposit Flow

1. Validate basket is `active`, quantity > 0, token_amount matches exponent formula.
2. Validate batch vintage meets basket date criteria (`min_start_year`, `min_start_date`, `max_start_date`).
3. Decrement `tradable_amount`, increment `escrowed_amount` in `credit_balance`.
4. Insert `credit_basket_deposit` record.
5. Upsert `credit_basket_token` to credit basket tokens to the depositor.

### Withdrawal Flow

1. Validate basket is `active`, sufficient token balance.
2. If basket has `disable_auto_retire = FALSE`, force retirement on withdrawal.
3. Iterate deposits in FIFO order (oldest `batch_start_date` first).
4. For each deposit consumed: decrement `escrowed_amount` in original depositor's balance.
5. If retiring: credit withdrawer's `retired_amount`; increment `credit_batch.retired_quantity`.
6. If not retiring: credit withdrawer's `tradable_amount`.
7. Debit the withdrawer's `credit_basket_token.token_amount`.

### Cancel Deposit

Cancel returns credits from escrow back to tradable and zeroes the deposit record. Only the original depositor may cancel; the deposit must be in `deposited` status.

### Auto-Retire Propagation

If a basket has `disable_auto_retire = FALSE`, **all** withdrawals are forced to retire. This propagates through the basket to every credit consumed, ensuring the basket maintains its retirement guarantee.

### Curator Management

Only the current curator may transfer curatorship to a new address. Date criteria can be updated independently.

## Cross-Chain Bridge

The bridge module enables outbound (Kokonut → external chain) and inbound (external chain → Kokonut) credit transfers.

```bash
python3 -m services.credit_class.cli bridge out \
  --batch-id UUID --sender 0x1234 --target celo \
  --recipient 0x5678 --quantity 50

python3 -m services.credit_class.cli bridge in \
  --class-id UUID --source polygon --issuer 0x1234 \
  --recipient 0x5678 --quantity 100

python3 -m services.credit_class.cli bridge complete \
  --bridge-tx-id UUID --bridge-tx-hash 0xabc...

python3 -m services.credit_class.cli bridge list --direction outbound
```

### Allowed Chains

Stored in `ecocredit_params` under key `allowed_bridge_chains`, defaulting to `["celo", "gnosis"]`. The bridge module's internal source chain is always `"kokonut"`.

### Outbound Flow

1. Validate batch exists with sufficient `available_quantity`.
2. Validate `target_chain` is in the allowed list.
3. Insert `credit_bridge_transaction` with `direction = outbound`, `source_chain = kokonut`, status `pending`.
4. On `complete_bridge`: set status `completed`, record `bridge_tx_hash`.

### Inbound Flow

1. Insert `credit_bridge_transaction` with `direction = inbound`, `target_chain = kokonut`, status `pending`.
2. Include origin transaction provenance (`origin_tx_id`, `origin_tx_source`).
3. On `complete_bridge`: set status `completed`.

### Transaction Status

```text
pending → completed | failed | cancelled
```

## Retirement

The governed retirement flow uses a reservation pattern: credits are reserved first, then retired only after independent human confirmation. This applies to the legacy `carbon_credit` path via `services.analytics.carbon_credits`.

### Step 1: Reserve

```bash
python3 -m services.analytics.carbon_credits --retire \
  --credit-id UUID --tonnes 5 \
  --reason voluntary_retirement \
  --requested-by REQUESTER_UUID \
  --idempotency-key REQUEST_KEY
```

1. Validate `retired_tonnes > 0` and `requested_by` is provided.
2. Lock `carbon_credit` row (`FOR UPDATE`); must be status `verified` or `published`.
3. Check idempotency: if `idempotency_key` already exists for this credit, return existing record; if different credit, error.
4. Compute `value = retired_tonnes × effective_price_per_tonne_usd`.
5. Atomically increment `carbon_credit.reserved_tonnes` WHERE `issuable - retired - reserved >= quantity`.
6. Insert `credit_retirement` with status `draft`, recording idempotency_key.

### Step 2: Human Review

```bash
python3 -m services.analytics.carbon_credits --confirm-retirement \
  --retirement-id UUID --reviewer-id REVIEWER_UUID

python3 -m services.analytics.carbon_credits --reject-retirement \
  --retirement-id UUID --reviewer-id REVIEWER_UUID

python3 -m services.analytics.carbon_credits --cancel-retirement \
  --retirement-id UUID --reviewer-id REVIEWER_UUID
```

Three outcomes:

| Decision | Effect |
|----------|--------|
| **confirm** | Decrement `reserved_tonnes`, increment `retired_tonnes`; status `verified`; set `confirmed_at` |
| **reject** | Decrement `reserved_tonnes` only; status `rejected` |
| **cancel** | Decrement `reserved_tonnes` only; status `cancelled`; set `cancelled_at` |

### Separation of Duties

The `reviewer_id` must differ from `created_by`. This is enforced by the `chk_credit_retire_approval` database check: a retirement can only reach `verified` or `published` if `reviewer_id IS NOT NULL`, `review_date IS NOT NULL`, `confirmed_at IS NOT NULL`, and `reviewer_id != created_by`.

### Idempotency

`credit_retirement` has a `UNIQUE` index on `idempotency_key`. Repeated retirement requests with the same key return the existing record. This prevents double-reservation on network retries.

### Reservation Pattern

Retirement does **not** immediately decrement available supply. It increments `reserved_tonnes` atomically. Only on human confirmation does `reserved_tonnes` decrement and `retired_tonnes` increment. This ensures:
- The requester cannot retroactively increase retired supply.
- The reviewer sees the reservation before confirming.
- Cancel or reject releases the reservation without affecting retired supply.

## Parameters

`ecocredit_params` stores module-wide configuration. All values are JSONB.

```bash
python3 -m services.credit_class.cli params list
python3 -m services.credit_class.cli params get --key class_fee
```

| Key | Default | Description |
|-----|---------|-------------|
| `class_fee` | `{"denom":"cusd","amount":0}` | Fee for class creation |
| `basket_fee` | `{"denom":"cusd","amount":0}` | Fee for basket creation |
| `allowed_bridge_chains` | `["celo","gnosis"]` | Chains allowed for bridging |
| `marketplace_buyer_fee` | `"0.03"` | Buyer fee rate (3%) |
| `marketplace_seller_fee` | `"0.03"` | Seller fee rate (3%) |
| `marketplace_fee_pool_address` | `null` | Fee pool recipient |

## Invariants And Recovery

1. **Supply invariant:** `retired_tonnes + reserved_tonnes <= issuable_tonnes` (`carbon_credit`); `issued_quantity - retired_quantity - cancelled_quantity >= 0` (`credit_batch`).
2. **Balance non-negative:** `tradable_amount >= 0`, `retired_amount >= 0`, `escrowed_amount >= 0` at all times. `upsert_balance` enforces this atomically.
3. **Escrow locks credits:** Sell order creation moves credits from tradable to escrow. Escrow is released on cancel/expire or consumed on fill. Escrow is not retirement.
4. **Approval separation:** Retirement reviewer must differ from requester (`reviewer_id != created_by`).
5. **Idempotency:** Duplicate retirement requests with the same key return the existing record; no double-reservation.
6. **Reservation before retirement:** Credits are reserved first; only human confirmation moves them to retired. Cancellation or rejection releases the reservation.
7. **Published requires evidence level 6:** `carbon_credit` status `published` requires `evidence_maturity = 6`, non-empty `external_verifier`, and non-empty `methodology_ref`.
8. **Public views require verified registry:** `v_public_carbon_credit_inventory` and `v_carbon_credit_balance` require a verified or published `farm_registry_record` for the location.
9. **Batch issue requires issuer authorization:** `issue_batch` checks `credit_class_issuer` for a non-revoked row matching the batch's credit class and the issuer address.
10. **Basket deposit criteria:** Vintage year must satisfy the basket's `min_start_year`, `min_start_date`, and `max_start_date` constraints. Token amount must match `quantity × 10^exponent`.
11. **Auto-retire propagation:** A basket with `disable_auto_retire = FALSE` forces retirement on all withdrawals. A sell order with auto-retire enabled cannot be disabled by the buyer.
12. **Fee cap:** A buy order's calculated buyer fee must not exceed `max_fee_amount` if provided.

### Recovery Guidance

- On a failed transaction, inspect batch status, balances, order/retirement status, and application logs before retrying.
- Reuse the original retirement idempotency key; do not generate a new one.
- Do not manually reconcile one side of a balance move. Correct the cause and re-run the transactional operation, or apply an audited migration.
- On ledger inconsistency, inspect `credit_balance` compartments against `credit_sell_order.escrow_quantity` and `credit_retirement.reserved_tonnes` to identify the drift source.

## Cross-References

- [Agent Safety](agent-safety.md) — agent write constraints and governed collection enforcement
- [Platform Integrity](platform-integrity.md) — schema constraints and migration discipline
- [Migrations](migrations.md) — ordered, checksummed migration workflow
- [Metric Verification](metric-verification.md) — evidence maturity levels and verification gates
- [Attestation Guide](attestation-guide.md) — EAS attestation for credits and retirement records
