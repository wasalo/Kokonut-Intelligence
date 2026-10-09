# @kokonut-intelligence/sdk

JavaScript/TypeScript SDK for the Kokonut Intelligence Platform. Typed REST client wrapping Directus collections for farm, crop, harvest, sales, expenses, sensors, attestations, and reports.

> This SDK covers Directus REST operations only. For gRPC services (IRI, content hash, ecocredit classes/batches/balances, marketplace, bridge), use `sdk/typescript/`.

## Install

```bash
npm install @kokonut-intelligence/sdk
```

## Build

```bash
npm run build
```

## Test

```bash
npm test
```

## Usage

```typescript
import { KokonutClient } from '@kokonut-intelligence/sdk';

const client = new KokonutClient('http://localhost:8055', { token: 'your-token' });

// List locations
const locations = await client.locations.list({ limit: 10 });

// Get a farm by ID
const farm = await client.farms.get('farm-uuid');

// List crop cycles for a plot
const cycles = await client.cropCycles.listByPlot('plot-uuid');

// Create a harvest event
const harvest = await client.harvestEvents.create({
  crop_cycle_id: 'cycle-uuid',
  plot_id: 'plot-uuid',
  location_id: 'location-uuid',
  harvest_date: '2026-07-15',
  quantity: 500,
  unit: 'kg',
  status: 'draft',
});

// Query unpaid sales
const unpaid = await client.salesEvents.listUnpaid();

// List sensor readings with anomalies
const anomalies = await client.sensorReadings.listAnomalies();
```

## Authentication

```typescript
// Login with email/password
const { token, refreshToken } = await client.login('user@example.com', 'password');

// Logout
await client.logout();
```

## Pagination

```typescript
// Page-based
const page1 = await client.locations.list({ page: 1, limit: 20 });

// Offset-based (automatically converted to page-based)
const offsetResults = await client.locations.list({ offset: 40, limit: 20 });
```

## Method Groups

| Group | Collection | Extra Methods |
|-------|-----------|---------------|
| `locations` | `location` | — |
| `farms` | `farm` | `listByLocation` |
| `plots` | `plot` | `listByFarm` |
| `cropCycles` | `crop_cycle` | `listByPlot`, `listActive` |
| `harvestEvents` | `harvest_event` | `listByCropCycle` |
| `salesEvents` | `sales_event` | `listByCropCycle`, `listUnpaid` |
| `expenseEvents` | `expense_event` | `listByCropCycle`, `listPendingApproval` |
| `sensorReadings` | `sensor_reading` | `listByDevice`, `listByPlot`, `listAnomalies` |
| `walletProfiles` | `wallet_profile` | `findByAddress` |
| `attestations` | `attestation_record` | `listPending`, `listByEntity` |
| `reports` | `report_snapshot` | `listByType` |
| `exports` | `export_log` | — |
| `noi` | `noi_snapshot` | `listByCropCycle` |

All groups inherit `GenericMethods`: `list`, `get`, `create`, `createMany`, `update`, `delete`.

## Examples

See `examples/` for runnable scripts:

```bash
npx tsx examples/create-farm.ts
npx tsx examples/query-noi.ts
npx tsx examples/sensor-data.ts
npx tsx examples/pagination-and-errors.ts
npx tsx examples/workflow.ts
```
