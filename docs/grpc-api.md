# gRPC API

Kokonut Intelligence exposes a gRPC API for high-performance, type-safe external integrations.

## Overview

The gRPC API runs alongside the existing Directus REST/GraphQL layer and Metadata API. It provides:

- **Type-safe messages** defined in Protobuf (`.proto` files)
- **Server-side streaming** for real-time data (balances, sell orders, sensor data)
- **API key authentication** via the existing `api_key` table
- **Client code generation** for Python, TypeScript, and React

## Architecture

```
Clients (Python/TypeScript/React)
    │
    ▼
gRPC Server (port 50051)
    │
    ├── API Key Interceptor (validates against api_key table)
    ├── Logging Interceptor
    │
    ├── EcocreditService
    │   ├── Classes, Batches, Balances, Baskets, Marketplace
    │   └── Streaming: StreamBalances, StreamBatchUpdates, StreamSellOrders
    │
    └── DataService
        ├── IRI operations (generate, resolve, history)
        ├── Content hash operations
        ├── Resolver operations
        ├── Attestor operations
        └── Streaming: StreamNewIRIs
```

## Running the Server

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Generate protobuf Python code
python -m grpc_tools.protoc \
    -I proto \
    --python_out=sdk/python/generated \
    --grpc_python_out=sdk/python/generated \
    proto/common/pagination.proto \
    proto/ecocredit/v1/types.proto \
    proto/ecocredit/v1/service.proto \
    proto/data/v1/types.proto \
    proto/data/v1/service.proto

# Start the server
python -m services.grpc.cli serve
```

### Docker

```bash
docker compose up grpc
```

The gRPC server runs on port 50051.

## Authentication

All gRPC calls require an API key passed via metadata:

```python
import grpc

metadata = [("x-api-key", "kk_live_your_api_key_here")]
response = stub.Classes ClassesRequest(), metadata=metadata)
```

API keys are validated against the `api_key` table. Keys must be:
- Active (`is_active = TRUE`)
- Not expired (`expires_at > NOW()`)
- Have appropriate scopes for the requested operation

## Streaming RPCs

The gRPC server supports server-side streaming for real-time data:

| RPC | Stream Type | Update Interval | Description |
|-----|-------------|-----------------|-------------|
| `StreamBalances` | Server → Client | 5 seconds | Live balance updates for an account |
| `StreamBatchUpdates` | Server → Client | 5 seconds | Batch status and quantity changes |
| `StreamSellOrders` | Server → Client | 5 seconds | Sell order updates |
| `StreamNewIRIs` | Server → Client | 5 seconds | New IRI registrations |

### Python Streaming Example

```python
import grpc
from services.grpc import ecocredit_pb2, ecocredit_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = ecocredit_pb2_grpc.EcocreditServiceStub(channel)

metadata = [("x-api-key", "kk_live_your_key")]

for update in stub.StreamBalances(
    ecocredit_pb2.StreamBalancesRequest(account_address="0x1234..."),
    metadata=metadata,
):
    print(f"Balance update: {update.account_address} "
          f"tradable={update.tradable_amount} "
          f"retired={update.retired_amount}")
```

### TypeScript Streaming Example

```typescript
import { EcocreditServiceClient } from "@kokonut/intelligence-client";

const client = new EcocreditServiceClient("localhost:50051", credentials.createInsecure());
const stream = client.streamBalances(
  { accountAddress: "0x1234..." },
  { "x-api-key": "kk_live_your_key" }
);

stream.on("data", (update) => {
  console.log(`Balance: ${update.accountAddress} tradable=${update.tradableAmount}`);
});
```

## Services

### EcocreditService

| RPC | Type | Description |
|-----|------|-------------|
| `Classes` | Unary | List all credit classes |
| `Class` | Unary | Get credit class by ID |
| `ClassesByAdmin` | Unary | List classes by admin |
| `ClassIssuers` | Unary | List issuers for a class |
| `CreateClass` | Unary | Create a credit class |
| `UpdateClass` | Unary | Update a credit class |
| `Projects` | Unary | List all projects |
| `Project` | Unary | Get project by ID |
| `ProjectsByClass` | Unary | List projects by class |
| `Batches` | Unary | List all batches |
| `Batch` | Unary | Get batch by ID |
| `BatchesByClass` | Unary | List batches by class |
| `BatchesByProject` | Unary | List batches by project |
| `CreateBatch` | Unary | Create a credit batch |
| `Balance` | Unary | Get balance for batch+account |
| `Balances` | Unary | Get all balances for account |
| `BalancesByBatch` | Unary | Get all balances for batch |
| `Supply` | Unary | Get supply for batch |
| `StreamBalances` | Server stream | Live balance updates |
| `StreamBatchUpdates` | Server stream | Batch update events |
| `Baskets` | Unary | List all baskets |
| `Basket` | Unary | Get basket by ID |
| `CreateBasket` | Unary | Create a basket |
| `PutInBasket` | Unary | Deposit credits into basket |
| `TakeFromBasket` | Unary | Withdraw credits from basket |
| `SellOrders` | Unary | List sell orders |
| `SellOrder` | Unary | Get sell order by ID |
| `CreateSellOrder` | Unary | Create sell order |
| `UpdateSellOrder` | Unary | Update sell order |
| `CancelSellOrder` | Unary | Cancel sell order |
| `CreateBuyOrder` | Unary | Create buy order |
| `ExecuteBuyOrder` | Unary | Execute buy order |
| `StreamSellOrders` | Server stream | Sell order updates |
| `AllowedDenoms` | Unary | List allowed denominations |
| `GetFeeParams` | Unary | Get marketplace fee params |
| `BridgeOut` | Unary | Bridge credits to another chain |
| `BridgeIn` | Unary | Bridge credits from another chain |
| `BridgeComplete` | Unary | Complete bridge transaction |
| `ApplyToClass` | Unary | Apply to credit class |
| `EvaluateApplication` | Unary | Evaluate application |
| `ListEnrollments` | Unary | List enrollments |
| `CreditTypes` | Unary | List credit types |

### DataService

| RPC | Type | Description |
|-----|------|-------------|
| `GenerateIRI` | Unary | Generate a new IRI |
| `ResolveIRI` | Unary | Resolve IRI to metadata |
| `GetVersionHistory` | Unary | Get IRI version history |
| `ComputeContentHash` | Unary | Compute content hash |
| `CreateContentHash` | Unary | Create content hash entry |
| `FindIRIByHash` | Unary | Find IRI by content hash |
| `DefineResolver` | Unary | Define a resolver URL |
| `RegisterToResolver` | Unary | Register data to resolver |
| `GetResolversForIRI` | Unary | Get resolvers for IRI |
| `ListResolvers` | Unary | List all resolvers |
| `AttestToIRI` | Unary | Attest to an IRI |
| `GetAttestorsForIRI` | Unary | Get attestors for IRI |
| `StreamNewIRIs` | Server stream | New IRI registration events |

## Client Generation

### Python

```bash
buf generate proto --template proto/buf.gen.yaml --include-imports
```

### TypeScript/React

```bash
cd sdk/typescript
npm install
npm run generate
npm run build
```

## Buf Cloud

The project uses Buf Cloud for hosted proto registry and CI/CD:

- **Proto registry**: `buf.build/kokonut/intelligence`
- **Breaking change detection**: Automated on every PR
- **Linting**: Enforced via `proto/buf.yaml`

## Health Check

```bash
# Via gRPC
python -m services.grpc.cli health --target localhost:50051

# Via Docker
docker compose exec grpc python -m services.grpc.cli health
```
