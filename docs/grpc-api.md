# gRPC API

Kokonut Intelligence provides a protobuf-defined gRPC server for typed
integrations with credit-class, marketplace, linked-data, and health services.
The gRPC API is a separate application boundary from Directus, the Gateway, and
the Metadata API.

The current server is an internal or network-restricted service. It listens with
plaintext gRPC, authenticates application calls with an API key from request
metadata, uses PostgreSQL for API-key and service data, and supports unary and
server-streaming RPCs.

## Current Boundaries

- The transport is insecure plaintext gRPC; the server does not configure TLS.
- Application RPCs require `x-api-key` metadata.
- Health `Check` and reflection are authentication-exempt. Health `Watch` is
  implemented but is not in the interceptor exemption list and therefore
  requires `x-api-key`.
- API keys are read from the PostgreSQL `api_key` table, not from the Gateway's
  environment-backed key configuration.
- The interceptor validates key hash, active state, and expiry. It loads roles
  and scopes but does not currently enforce operation-level scopes.
- Streaming RPCs poll PostgreSQL every five seconds; they are not event-driven
  pub/sub streams.
- Production Compose removes host port exposure, and the production Caddy
  configuration does not proxy gRPC. External access requires separate network
  or reverse-proxy configuration.

Do not expose plaintext gRPC directly to an untrusted network. Put it behind a
TLS-capable gRPC reverse proxy or use a private network with an independently
managed security boundary.

## Architecture

```text
Client
  |
  | plaintext gRPC on the configured internal endpoint
  v
gRPC server
  |
  +-- LoggingInterceptor
  +-- APIKeyInterceptor
  |     +-- SHA-256 request key
  |     +-- PostgreSQL api_key lookup
  |     +-- active/expiry checks
  |     +-- auth context for service handlers
  |
  +-- grpc.health.v1.Health
  +-- grpc.reflection.v1alpha.ServerReflection
  +-- ecocredit.v1.EcocreditService
  +-- data.v1.DataService
  |
  +-- ThreadPoolExecutor (GRPC_MAX_WORKERS)
  +-- ThreadedConnectionPool (GRPC_DB_MIN_CONN..GRPC_DB_MAX_CONN)
  +-- PostgreSQL
```

The server registers credit and data services when their generated Python
modules import successfully. If an optional service import fails, the server
logs a warning and continues with the services that were registered.

## Services

### Registered Services

| Service | Package | Purpose |
|---|---|---|
| `Health` | `grpc.health.v1` | Liveness/readiness-style gRPC status |
| `ServerReflection` | `grpc.reflection.v1alpha` | Runtime service discovery |
| `EcocreditService` | `ecocredit.v1` | Credit classes, projects, batches, balances, baskets, marketplace, bridge, and enrollment operations |
| `DataService` | `data.v1` | IRI, content hash, resolver, and attestor operations |

The authoritative service definitions are:

- `proto/ecocredit/v1/service.proto`
- `proto/data/v1/service.proto`
- the standard gRPC health protocol
- the standard gRPC reflection protocol

### EcocreditService RPCs

#### Class Queries And Mutations

| RPC | Mode | Request purpose |
|---|---|---|
| `Classes` | Unary | List credit classes with pagination |
| `Class` | Unary | Get a class by `class_id` |
| `ClassesByAdmin` | Unary | List classes by admin address with pagination |
| `ClassIssuers` | Unary | List issuers for a class |
| `CreateClass` | Unary | Create a credit class |
| `UpdateClass` | Unary | Update class metadata and status fields |

`CreateClass` accepts name, methodology, credit type, description, URL, admin
address, and issuer addresses. `UpdateClass` accepts class ID, name,
description, URL, methodology, status, and serialized metadata.

#### Project Queries

| RPC | Mode | Request purpose |
|---|---|---|
| `Projects` | Unary | List projects with pagination |
| `Project` | Unary | Get a project by location ID |
| `ProjectsByClass` | Unary | List projects for a credit class with pagination |

#### Batch Queries And Creation

| RPC | Mode | Request purpose |
|---|---|---|
| `Batches` | Unary | List batches with pagination |
| `Batch` | Unary | Get a batch by batch ID |
| `BatchesByClass` | Unary | List batches for a class with pagination |
| `BatchesByProject` | Unary | List batches for a project/location with pagination |
| `CreateBatch` | Unary | Create a credit batch |

`CreateBatch` accepts credit class ID, location ID, vintage year, total quantity,
unit, and jurisdiction. It returns the batch ID and batch code.

#### Balance Queries

| RPC | Mode | Request purpose |
|---|---|---|
| `Balance` | Unary | Get one batch/account balance |
| `Balances` | Unary | List balances for an account |
| `BalancesByBatch` | Unary | List balances for a batch |
| `Supply` | Unary | Get tradable, retired, and escrowed supply for a batch |

#### Balance And Batch Streams

| RPC | Mode | Request purpose |
|---|---|---|
| `StreamBalances` | Server stream | Poll balances for an account and emit balance updates |
| `StreamBatchUpdates` | Server stream | Poll batch rows updated since the previous check |

#### Baskets

| RPC | Mode | Request purpose |
|---|---|---|
| `Baskets` | Unary | List baskets with pagination |
| `Basket` | Unary | Get a basket by ID |
| `CreateBasket` | Unary | Create a basket |
| `PutInBasket` | Unary | Deposit credits into a basket |
| `TakeFromBasket` | Unary | Withdraw basket tokens for credits, optionally retiring them |

#### Marketplace

| RPC | Mode | Request purpose |
|---|---|---|
| `SellOrders` | Unary | List sell orders, optionally filtered by batch or seller |
| `SellOrder` | Unary | Get a sell order by ID |
| `CreateSellOrder` | Unary | Create a sell order |
| `UpdateSellOrder` | Unary | Update quantity, price, or expiration |
| `CancelSellOrder` | Unary | Cancel a seller's order |
| `CreateBuyOrder` | Unary | Create a buy order |
| `ExecuteBuyOrder` | Unary | Execute a buy order |
| `StreamSellOrders` | Server stream | Poll updated sell orders and emit order updates |
| `AllowedDenoms` | Unary | List allowed marketplace denominations |
| `GetFeeParams` | Unary | Get marketplace fee parameters |

Marketplace messages include seller/buyer addresses, quantity, ask price and
denomination, expiration, partial-fill behavior, retirement options, and buyer
fee limits. The protobuf fields are the source of truth for exact names and
types.

#### Bridge And Enrollment

| RPC | Mode | Request purpose |
|---|---|---|
| `BridgeOut` | Unary | Create an outbound bridge record |
| `BridgeIn` | Unary | Create an inbound bridge record |
| `BridgeComplete` | Unary | Complete a bridge transaction with its transaction hash |
| `ApplyToClass` | Unary | Apply a location to a credit class |
| `EvaluateApplication` | Unary | Update an enrollment/application status |
| `ListEnrollments` | Unary | List enrollments by location and/or class |
| `CreditTypes` | Unary | List configured credit types |

The gRPC bridge methods create or update database records. They do not submit
blockchain transactions. Any on-chain execution remains outside this service
and must follow the platform's human-approved write boundaries.

### DataService RPCs

#### IRI And Content Hash Operations

| RPC | Mode | Request purpose |
|---|---|---|
| `GenerateIRI` | Unary | Generate an IRI for an entity and optional metadata/hash parameters |
| `ResolveIRI` | Unary | Resolve an IRI to metadata |
| `GetVersionHistory` | Unary | List IRI versions for an entity |
| `ComputeContentHash` | Unary | Compute a content hash for data and content metadata |
| `CreateContentHash` | Unary | Persist a content hash entry for an IRI |
| `FindIRIByHash` | Unary | Find IRI records by hash value |

`GenerateIRI` accepts `entity_type`, `entity_id`, `metadata_json`,
`content_hash_type`, and `algorithm`. `ComputeContentHash` accepts data,
algorithm, content type, and media type.

#### Resolver Operations

| RPC | Mode | Request purpose |
|---|---|---|
| `DefineResolver` | Unary | Define a resolver URL and manager |
| `RegisterToResolver` | Unary | Register an IRI with a resolver |
| `GetResolversForIRI` | Unary | List resolvers registered for an IRI |
| `ListResolvers` | Unary | List resolvers, optionally by manager |

#### Attestor Operations

| RPC | Mode | Request purpose |
|---|---|---|
| `AttestToIRI` | Unary | Create or return an attestation association for an IRI |
| `GetAttestorsForIRI` | Unary | List attestors associated with an IRI |

#### IRI Stream

| RPC | Mode | Request purpose |
|---|---|---|
| `StreamNewIRIs` | Server stream | Poll newly created IRI records and emit updates |

## Protobuf Messages

The proto files also define shared pagination and domain messages.

### Pagination

List RPCs use `common.PageRequest` and return `common.PageResponse` where
declared. The exact page fields are defined in:

```text
proto/common/pagination.proto
```

Do not assume every list RPC is paginated. For example, `ClassIssuers`,
`Balances`, `BalancesByBatch`, `ListEnrollments`, and resolver/attestor list
operations use their declared repeated response fields without a pagination
message.

### Data Types

The complete domain message and field definitions are in:

- `proto/ecocredit/v1/types.proto`
- `proto/ecocredit/v1/service.proto`
- `proto/data/v1/types.proto`
- `proto/data/v1/service.proto`

The `.proto` definitions, not this guide, are authoritative for field numbers,
wire types, optionality, and compatibility.

## Authentication

### Request Metadata

Every application RPC must include the exact lowercase metadata key:

```text
x-api-key: <raw API key>
```

The interceptor does not accept the Gateway's `api-key` compatibility alias. A
missing key returns `UNAUTHENTICATED` with `Missing x-api-key metadata`.

Example:

```python
import grpc

from services.grpc.ecocredit.v1 import service_pb2, service_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = service_pb2_grpc.EcocreditServiceStub(channel)
metadata = [("x-api-key", "kk_live_your_api_key")]

response = stub.Classes(
    service_pb2.ClassesRequest(),
    metadata=metadata,
)
```

Do not commit, print, or place real credentials in examples, source files, or
logs.

### PostgreSQL Lookup

The interceptor:

1. Hashes the supplied key with SHA-256.
2. Queries `api_key.key_hash`.
3. Loads `is_active`, `expires_at`, `scopes`, and the related app role.
4. Rejects missing or invalid keys.
5. Rejects deactivated keys with `PERMISSION_DENIED`.
6. Rejects expired keys with `PERMISSION_DENIED`.
7. Propagates API-key ID, role name, and scopes through a context variable.

The current interceptor does not compare the loaded scopes against the RPC
being called. The guide must therefore not promise per-RPC scope enforcement.
That is a security gap to address separately before treating scopes as an
authorization guarantee.

### Exempt RPCs

These exact method paths bypass API-key authentication:

```text
grpc.health.v1.Health/Check
```

Although `Health/Watch` is implemented, it is not exempt and requires the same
API-key metadata as application RPCs.

Reflection can disclose registered service and protobuf descriptors. Restrict
network access if reflection should not be externally visible.

## Health And Reflection

The health service implements the standard gRPC health protocol:

```bash
python3 -m services.grpc.cli health --target localhost:50051
```

Successful output reports the protobuf health status, normally `SERVING`.
Health failures print the gRPC error and exit with status `1`.

`Health/Check` returns `SERVING`. `Health/Watch` currently yields a single
`SERVING` response and does not continuously monitor service state.

The server enables reflection for the standard reflection service, health, and
the credit/data services that registered successfully.

## Server-Streaming Behavior

The server exposes four server-streaming RPCs:

| RPC | Poll interval | Source |
|---|---:|---|
| `StreamBalances` | 5 seconds | Account balances |
| `StreamBatchUpdates` | 5 seconds | `credit_batch.updated_at` |
| `StreamSellOrders` | 5 seconds | `credit_sell_order.updated_at` |
| `StreamNewIRIs` | 5 seconds | `iri_registry.created_at` |

These streams are polling loops:

- the handler keeps a PostgreSQL connection for the stream lifetime;
- `StreamBalances` emits the current account balances on each cycle;
- the other three streams query rows newer than the previous check;
- the loop continues while `context.is_active()`;
- cancellation exits the loop and closes the connection;
- there is no broker subscription or durable event cursor;
- updates can be delayed by up to the polling interval and can be affected by
  timestamp precision/cursor behavior.

Clients should handle normal stream cancellation, transient database failures,
and reconnect/backoff themselves. These streams should not be described as
strict real-time delivery or exactly-once event delivery.

### Python Stream Example

```python
import grpc

from services.grpc.ecocredit.v1 import service_pb2, service_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = service_pb2_grpc.EcocreditServiceStub(channel)

for update in stub.StreamBalances(
    service_pb2.StreamBalancesRequest(account_address="0x1234"),
    metadata=[("x-api-key", "kk_live_your_api_key")],
):
    print(
        update.batch_id,
        update.tradable_amount,
        update.retired_amount,
        update.escrowed_amount,
    )
```

The generated Python module path is available under `services/grpc` in the
Docker image. For local generation, configure `PYTHONPATH` as described below.

## Running The Server

### Local Development

Install Python dependencies, generate Python protobuf modules, then start the
server:

```bash
pip install -r requirements.txt

python -m grpc_tools.protoc \
  -I proto \
  --python_out=sdk/python/generated \
  --grpc_python_out=sdk/python/generated \
  proto/common/pagination.proto \
  proto/ecocredit/v1/types.proto \
  proto/ecocredit/v1/service.proto \
  proto/data/v1/types.proto \
  proto/data/v1/service.proto

export PYTHONPATH="$PWD/sdk/python/generated:$PYTHONPATH"
python3 -m services.grpc.cli serve
```

The server reads the PostgreSQL connection settings used by
`services.common.db`. The database must be reachable and contain the
`api_key`, role, credit, and linked-data tables required by the selected RPCs.

### Compose Development

```bash
docker compose up grpc
```

The Compose service:

- builds from `Dockerfile.grpc`;
- waits for the `database` health check;
- connects to PostgreSQL as the `database` Compose service;
- binds `127.0.0.1:50051:50051` on the host in the base Compose file;
- uses `GRPC_PORT=50051` and `GRPC_MAX_WORKERS=10` by default;
- connects to both `databases` and `apps` Docker networks.

Host port exposure is loopback-only in the base development configuration.

### Compose Production

`docker-compose.prod.yml` removes the gRPC host port mapping and sets a memory
limit. The production Caddy configuration does not contain a gRPC reverse-proxy
route. Production clients therefore need an explicitly configured internal
network path or a separately managed TLS-capable gRPC proxy.

Do not assume that the normal HTTP Caddy routes for Directus or Metabase expose
the gRPC service.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `GRPC_PORT` | `50051` | Server listen port |
| `GRPC_MAX_WORKERS` | `10` | gRPC thread-pool worker count |
| `GRPC_DB_MIN_CONN` | `2` | Minimum PostgreSQL pool connections |
| `GRPC_DB_MAX_CONN` | `20` | Maximum PostgreSQL pool connections |
| `PG_HOST` | service configuration | PostgreSQL host |
| `PG_PORT` | service configuration | PostgreSQL port |
| `PG_DB` | service configuration | PostgreSQL database |
| `PG_USER` | service configuration | PostgreSQL user |
| `PG_PASSWORD` | required in Compose | PostgreSQL password |

The server creates a `ThreadedConnectionPool` using the configured minimum and
maximum. Each unary handler returns its connection after the operation. Each
stream retains a connection until cancellation or stream termination.

The server handles `SIGTERM` and `SIGINT` by stopping with a 30-second grace
period before exiting.

## Error Handling

The service handlers use standard gRPC status codes for common conditions,
including:

| Condition | Typical status |
|---|---|
| Missing API key | `UNAUTHENTICATED` |
| Invalid API key | `UNAUTHENTICATED` |
| Deactivated API key | `PERMISSION_DENIED` |
| Expired API key | `PERMISSION_DENIED` |
| API-key lookup failure | `INTERNAL` |
| Missing requested record | `NOT_FOUND` |
| Invalid service operation | Service-specific gRPC error |

Exact status and message behavior is implemented in
`services/grpc/credit_class_service.py` and `services/grpc/data_service.py`.
Clients should branch on status codes rather than parsing message strings.

## Protobuf Generation

The repository uses Buf configuration in `proto/buf.yaml` and
`proto/buf.gen.yaml`.

The configured remote plugins generate:

- Python protobuf and gRPC Python modules under `sdk/python/generated`;
- TypeScript/Node protobuf and gRPC modules under `sdk/typescript/generated`.

Generate all configured outputs from the repository root with:

```bash
buf generate --config proto/buf.yaml --template proto/buf.gen.yaml
```

The TypeScript package also provides:

```bash
cd sdk/typescript
npm install
npm run generate
npm run build
```

`npm run generate` runs Buf from the repository root. Docker uses
`grpc_tools.protoc` for Python generation and copies generated packages into
`services/grpc` so the server can import them.

The Python package generated by the Docker build is not the same thing as the
Directus-oriented JavaScript SDK. Keep those integration paths separate.

## SDKs

### Python

Python protobuf modules are generated from the proto files. The server imports
the generated modules from `services/grpc/ecocredit/v1` and
`services/grpc/data/v1` after the Docker build copies them there.

For a local client, use the generated `*_pb2.py` and `*_pb2_grpc.py` modules and
ensure their output directory is on `PYTHONPATH`.

### TypeScript

The `sdk/typescript` package is named `@kokonut/intelligence-client` and
currently exposes a `KokonutGrpcClient` transport wrapper around
`@grpc/grpc-js`. Its default credentials are insecure unless the caller passes
channel credentials.

```typescript
import { credentials } from "@grpc/grpc-js";
import { KokonutGrpcClient } from "@kokonut/intelligence-client";

const client = new KokonutGrpcClient(
  "localhost:50051",
  { credentials: credentials.createInsecure() },
);

// Use generated service clients from sdk/typescript/generated.
// Add x-api-key through the generated call metadata.

client.close();
```

The generated service client exports and exact method signatures depend on the
Buf-generated output. The package does not currently provide a React-specific
client abstraction.

### JavaScript SDK

`sdk/javascript` is a separate Directus REST SDK. It provides collection,
authentication, reporting, export, and NOI methods through `@directus/sdk`; it
is not the gRPC client package described in this document.

Do not import gRPC service clients from `sdk/javascript` or describe that SDK as
protobuf-generated.

## Security Rules

1. Use TLS or a private trusted network before exposing the plaintext server.
2. Send API keys through gRPC metadata, never through protobuf message fields.
3. Store only hashed API keys in `api_key.key_hash` and protect raw keys at
   issuance and runtime.
4. Treat the current scope-loading behavior as authentication context, not
   enforced authorization.
5. Restrict reflection if service descriptors should not be public.
6. Bound stream counts because each active stream retains a PostgreSQL
   connection and a worker thread.
7. Use reconnect and backoff logic for polling stream cancellation or database
   errors.
8. Keep bridge, marketplace, attestation, and other write operations behind the
   platform's human-approval and governance boundaries.

## Health Command

```bash
python3 -m services.grpc.cli health --target localhost:50051
```

For a Compose container, the default target is the container's own
`localhost:50051`:

```bash
docker compose exec grpc python3 -m services.grpc.cli health
```

The command checks the standard gRPC health service, not an HTTP endpoint and
not the platform's broader `overall_health()` function.

## Tests And References

Focused tests:

- `tests/test_grpc.py`

Implementation references:

- `proto/common/pagination.proto`
- `proto/ecocredit/v1/types.proto`
- `proto/ecocredit/v1/service.proto`
- `proto/data/v1/types.proto`
- `proto/data/v1/service.proto`
- `services/grpc/server.py`
- `services/grpc/auth.py`
- `services/grpc/interceptors.py`
- `services/grpc/health.py`
- `services/grpc/credit_class_service.py`
- `services/grpc/data_service.py`
- `services/grpc/cli.py`
- `sdk/typescript/src/index.ts`
- `sdk/typescript/package.json`
- `sdk/javascript/src/client.ts`
- `proto/buf.yaml`
- `proto/buf.gen.yaml`
- `Dockerfile.grpc`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `config/caddy/Caddyfile.production`
