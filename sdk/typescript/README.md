# @kokonut/intelligence-client

TypeScript gRPC client for the Kokonut Intelligence Platform.

## Install

```bash
npm install @kokonut/intelligence-client
```

## Generate protobuf types

The `generated/` directory is gitignored. Regenerate after cloning:

```bash
npm run generate
```

Requires [Buf](https://buf.build) (`npx @bufbuild/buf`).

## Build

```bash
npm run build
```

## Usage

```ts
import { KokonutGrpcClient } from "@kokonut/intelligence-client";

const client = new KokonutGrpcClient("localhost:50051");

// ── DataService ───────────────────────────────────────────────────────

// Generate an IRI
const { iri } = await client.data.generateIRI({
  entityType: "location",
  entityId: "loc-001",
});

// Resolve an IRI
const resolved = await client.data.resolveIRI(iri);

// Compute a content hash
const hash = await client.data.computeContentHash({
  data: JSON.stringify({ name: "Test Farm" }),
  algorithm: "sha256",
});

// Stream new IRIs
for await (const update of client.data.streamNewIRIs("location")) {
  console.log("New IRI:", update.iri);
}

// ── EcocreditService ──────────────────────────────────────────────────

// List credit classes
const { classes } = await client.ecocredit.classes();

// Create a credit class
const { classId } = await client.ecocredit.createClass({
  name: "Kokonut Carbon",
  methodology: "IPCC 2006",
  creditType: "C",
  adminAddress: "0x...",
});

// List batches
const { batches } = await client.ecocredit.batches();

// Check balance
const { balance } = await client.ecocredit.balance(
  "batch-001",
  "0x...",
);

// Create a sell order
const { orderId } = await client.ecocredit.createSellOrder({
  creditBatchId: "batch-001",
  sellerAddress: "0x...",
  quantity: 100,
  askPrice: 25,
  askDenom: "cusd",
});

// Stream balance updates
for await (const update of client.ecocredit.streamBalances("0x...")) {
  console.log("Balance:", update.tradableAmount, update.retiredAmount);
}

client.close();
```

## Authentication

The gRPC server validates API keys via `x-api-key` metadata. Pass metadata to the client:

```ts
import { Metadata } from "@grpc/grpc-js";
import { KokonutGrpcClient } from "@kokonut/intelligence-client";

const metadata = new Metadata();
metadata.add("x-api-key", "your-api-key");

const client = new KokonutGrpcClient("localhost:50051", { metadata });
```

## Error handling

All gRPC errors are wrapped in typed error classes:

```ts
import {
  KokonutGrpcError,
  NotFoundError,
  UnauthenticatedError,
} from "@kokonut/intelligence-client";

try {
  await client.data.resolveIRI("nonexistent");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("IRI not found:", err.details);
  } else if (err instanceof UnauthenticatedError) {
    console.log("Auth failed");
  } else if (err instanceof KokonutGrpcError) {
    console.log("gRPC error:", err.code, err.message);
  }
}
```

| Error Class | gRPC Code | Meaning |
|---|---|---|
| `NotFoundError` | 5 | Resource not found |
| `PermissionDeniedError` | 7 | Insufficient permissions |
| `UnauthenticatedError` | 16 | Missing/invalid credentials |
| `InvalidArgumentError` | 3 | Malformed request |
| `InternalError` | 13 | Server-side error |
| `UnavailableError` | 14 | Server unreachable |

## API Reference

### `KokonutGrpcClient`

| Property | Type | Description |
|---|---|---|
| `data` | `DataServiceClient` | IRI, content hash, resolver, attestor operations |
| `ecocredit` | `EcocreditServiceClient` | Classes, batches, balances, baskets, marketplace, bridge |
| `close()` | `() => void` | Close all connections |

### `DataServiceClient`

| Method | Description |
|---|---|
| `generateIRI(req)` | Generate a new IRI |
| `resolveIRI(iri)` | Resolve an IRI to its metadata |
| `getVersionHistory(entityType, entityId)` | Get all versions of an IRI |
| `computeContentHash(req)` | Compute a content hash |
| `createContentHash(req)` | Store a content hash |
| `findIRIByHash(hashValue)` | Find IRI by content hash |
| `defineResolver(req)` | Register a new resolver |
| `registerToResolver(req)` | Link IRI to resolver |
| `getResolversForIRI(iriId)` | Get resolvers for an IRI |
| `listResolvers(managerAddress?)` | List all resolvers |
| `attestToIRI(req)` | Attest to an IRI |
| `getAttestorsForIRI(iriId)` | Get attestors for an IRI |
| `streamNewIRIs(entityType?)` | Stream new IRI registrations |

### `EcocreditServiceClient`

| Method | Description |
|---|---|
| `classes()` | List credit classes |
| `class(classId)` | Get a credit class |
| `classesByAdmin(admin)` | List classes by admin |
| `classIssuers(classId)` | List issuers for a class |
| `createClass(req)` | Create a credit class |
| `updateClass(req)` | Update a credit class |
| `projects()` | List projects |
| `project(locationId)` | Get a project |
| `projectsByClass(classId)` | List projects by class |
| `batches()` | List batches |
| `batch(batchId)` | Get a batch |
| `batchesByClass(classId)` | List batches by class |
| `batchesByProject(locationId)` | List batches by project |
| `createBatch(req)` | Create a batch |
| `balance(batchId, account)` | Get balance |
| `balances(account)` | List balances for account |
| `balancesByBatch(batchId)` | List balances for batch |
| `supply(batchId)` | Get batch supply |
| `streamBalances(account)` | Stream balance updates |
| `streamBatchUpdates(classId?)` | Stream batch updates |
| `baskets()` | List baskets |
| `basket(basketId)` | Get a basket |
| `createBasket(req)` | Create a basket |
| `putInBasket(req)` | Deposit credits into basket |
| `takeFromBasket(req)` | Withdraw from basket |
| `sellOrders(req?)` | List sell orders |
| `sellOrder(orderId)` | Get a sell order |
| `createSellOrder(req)` | Create a sell order |
| `updateSellOrder(req)` | Update a sell order |
| `cancelSellOrder(id, seller)` | Cancel a sell order |
| `createBuyOrder(req)` | Create a buy order |
| `executeBuyOrder(buyOrderId)` | Execute a buy order |
| `streamSellOrders(batchId?)` | Stream sell order updates |
| `allowedDenoms()` | List allowed denominations |
| `getFeeParams()` | Get fee parameters |
| `bridgeOut(req)` | Bridge credits out |
| `bridgeIn(req)` | Bridge credits in |
| `completeBridge(txId, hash?)` | Complete a bridge transaction |
| `applyToClass(req)` | Apply to a credit class |
| `evaluateApplication(req)` | Evaluate an application |
| `listEnrollments(req?)` | List enrollments |
| `creditTypes()` | List credit types |

## Development

```bash
npm install        # install deps
npm run generate   # generate protobuf types
npm run build      # compile TypeScript
npm test           # run tests
npm run lint       # type-check
```
