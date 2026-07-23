# Proto Definitions

gRPC service and message definitions for the Kokonut Intelligence platform. Compiled to Python stubs at Docker build time via `grpc_tools.protoc`.

## Directory Structure

```
proto/
├── buf.yaml              Buf v2 module config (lint + breaking change detection)
├── buf.gen.yaml          Buf code generation config (Python + TypeScript SDKs)
├── common/
│   └── pagination.proto  Shared PageRequest/PageResponse messages
├── data/v1/
│   ├── service.proto     DataService — IRI, content hash, resolver, attestor RPCs
│   └── types.proto       IRI, IRIInfo, ContentHashEntry, Resolver, AttestorEntry messages
└── ecocredit/v1/
    ├── service.proto     EcocreditService — classes, batches, balances, baskets, marketplace RPCs
    └── types.proto       CreditClass, Batch, Balance, Basket, SellOrder, and related messages
```

## Services

### DataService (13 RPCs)

| Category | RPCs |
|----------|------|
| IRI operations | `GenerateIRI`, `ResolveIRI`, `GetVersionHistory` |
| Content hash | `ComputeContentHash`, `CreateContentHash`, `FindIRIByHash` |
| Resolver | `DefineResolver`, `RegisterToResolver`, `GetResolversForIRI`, `ListResolvers` |
| Attestor | `AttestToIRI`, `GetAttestorsForIRI` |
| Streaming | `StreamNewIRIs` (server-streaming) |

Implementation: `services/grpc/data_service.py`

### EcocreditService (35 RPCs)

| Category | RPCs |
|----------|------|
| Class queries | `Classes`, `Class`, `ClassesByAdmin`, `ClassIssuers` |
| Class mutations | `CreateClass`, `UpdateClass` |
| Project queries | `Projects`, `Project`, `ProjectsByClass` |
| Batch queries | `Batches`, `Batch`, `BatchesByClass`, `BatchesByProject` |
| Batch mutations | `CreateBatch` |
| Balance queries | `Balance`, `Balances`, `BalancesByBatch`, `Supply` |
| Streaming | `StreamBalances`, `StreamBatchUpdates` (server-streaming) |
| Basket | `Baskets`, `Basket`, `CreateBasket`, `PutInBasket`, `TakeFromBasket` |
| Marketplace | `SellOrders`, `SellOrder`, `CreateSellOrder`, `UpdateSellOrder`, `CancelSellOrder`, `CreateBuyOrder`, `ExecuteBuyOrder`, `StreamSellOrders` |
| Allowed denoms | `AllowedDenoms` |
| Fee params | `GetFeeParams` |
| Bridge | `BridgeOut`, `BridgeIn`, `BridgeComplete` |
| Enrollment | `ApplyToClass`, `EvaluateApplication`, `ListEnrollments` |
| Credit types | `CreditTypes` |

Implementation: `services/grpc/credit_class_service.py`

## Code Generation

### Docker Build (primary)

`Dockerfile.grpc` compiles proto files at build time:

```dockerfile
RUN python -m grpc_tools.protoc \
    -I proto \
    --python_out=sdk/python/generated \
    --grpc_python_out=sdk/python/generated \
    proto/common/pagination.proto \
    proto/data/v1/types.proto proto/data/v1/service.proto \
    proto/ecocredit/v1/types.proto proto/ecocredit/v1/service.proto
```

Generated `_pb2.py` files are **not committed** — they exist only inside the Docker image.

### Local SDK Generation (buf)

For local development or TypeScript SDK:

```bash
cd proto
buf generate
```

Requires `buf` CLI installed. Generates to `sdk/python/generated/` and `sdk/typescript/generated/`.

## Linting

```bash
cd proto
buf lint
```

Uses STANDARD + COMMENTS rules with exceptions for `UNARY_RPC` and `COMMENT_FIELD`.

## Relationship to services/grpc/

The Python service implementations (`data_service.py`, `credit_class_service.py`) import generated `_pb2` modules from `services/grpc/data/v1/` and `services/grpc/ecocredit/v1/`. These directories are populated by `Dockerfile.grpc` at build time.

If generated files are missing (local development without Docker), the server starts anyway — service registration is wrapped in `try/except ImportError`.

## Adding New RPCs

1. Add the RPC and messages to the appropriate `service.proto` and `types.proto`
2. Implement the method in `services/grpc/data_service.py` or `services/grpc/credit_class_service.py`
3. The method signature must match: `def MethodName(self, request, context):`
4. Rebuild the gRPC Docker image: `docker compose build grpc`
