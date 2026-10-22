# Optional Kernel gRPC transport

`docker-compose.kernel-grpc.yml` adds one transport service to the standalone
candidate. The API/worker app remains independent of gRPC and keeps its provider
disabled. The transport enables gRPC only in its own process, connects to the
private database, and requires no ClickHouse credentials.

The service has no host port mapping. Its internal address is `grpc:50051` on
the candidate network. Four RPC workers and a one-to-five connection pool are
initial conservative settings, not measured capacity guarantees. Compose adds
init, restart policy, a forty-second shutdown grace, and the existing health
RPC check. The health service reports serving; this does not verify all RPC
registrations, database queries, or authorization behavior.

## Explicit deployment boundary

- The profile is opt-in. The default app has `KOKONUT_FEATURE_GRPC=false` and
  does not install the gRPC dependencies. Omitting the profile leaves REST and
  native CLI access independent of gRPC.
- Port 50051 is available only to peers on the private Compose `kernel`
  network. The overlay publishes no host port. The Caddy profile routes traffic
  to the Gateway and does not proxy gRPC.
- The overlay supplies no `GRPC_TLS_CERT` or `GRPC_TLS_KEY` and explicitly sets
  `GRPC_ALLOW_INSECURE=true` because the listener is reachable only on the
  private candidate network and has no host port. This is a deliberate
  private-network transport choice, not public ingress. Production Compose
  forces the setting off; the server refuses to start without a certificate
  and key unless a trusted private deployment explicitly opts in. A
  deployment-specific override can mount the server certificate/key and CA
  bundle read-only and set their container paths; the health command uses
  `GRPC_TLS_CA` for TLS and fails closed if server TLS is configured without
  that trust path.
- The API-key interceptor and method/resource scopes are the RPC authorization
  boundary; the profile does not provision an API key. Health/reflection checks
  do not establish business-method authorization.
- `PG_USER` defaults to `kokonut` if `KOKONUT_RUNTIME_USER` is unset, and the
  password falls back to `POSTGRES_PASSWORD`. That compatibility default may
  be owner-level access. Select the reviewed non-owner runtime identity and
  matching secret before treating this as a least-privilege deployment.
- Four workers, pool bounds 1–5, and the server's 30-second graceful stop are
  sizing/shutdown defaults, not measured capacity or complete cancellation
  guarantees. Compose allows 40 seconds before container termination.
- No schema migration is needed to start the transport. The current candidate
  schema already includes migrations through 379, but this does not enable or
  certify the optional service.

## Image and preparation

`Dockerfile.kernel` now has a shared `kernel-base`, optional `grpc` target, and
final/default `kernel` target. The default image does not install grpcio or
protobuf tooling. The gRPC target adds only requirements/grpc.txt to the existing
Kernel dependencies. It generates the current common/ecocredit/data protobufs
in the image, copies the packages to the service import paths, and adds the
generated root to PYTHONPATH, following the legacy image's import arrangement.
No generated artifacts are written to the checkout. The service runs as UID
10001 and overrides the API command and healthcheck.

Preparation commands, after loading encrypted settings:

```sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-grpc.yml config --quiet
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-grpc.yml build grpc
```

Merged Compose configuration was validated with a placeholder database password
without printing resolved configuration or secrets. The transport image was
subsequently built successfully as recorded below. No service start, key
provisioning, or runtime RPC tests were performed. The running candidate and
stopped legacy stack were not changed.

## First transport build evidence

Local Docker build completed for target `grpc` on 10 October 2026:

- Tag: `kokonut-kernel-candidate-grpc:local`.
- Inspected image identity:
  `sha256:66a1cfa9b0b82ade8b4ebf16a5c7db7bf162d57752b3ffa452558a5dcd8234bf`.
- Platform: linux/amd64; configured user: appuser (created as UID 10001).
- Local reported size: 516,712,527 bytes, approximately 493 MiB; not runtime RAM
  usage or compressed registry transfer size.
- Resolved grpcio 1.84.0, grpcio-tools/reflection/health-checking 1.81.1, and
  protobuf 6.33.6 within the inherited requirement constraints.
- Protobuf generation completed; protoc reported two unused pagination imports.

This establishes successful dependency installation and code generation, not
runtime import/handler compatibility or ARM64 certification. The image captures
uncommitted source at build time; later changes require rebuilding. It has not
been tagged as a release or used to replace any running service.

## Adoption and acceptance

### Corrected transport rebuild

The same local tag was rebuilt successfully on 10 October 2026 after the pooled
database, authentication context/scope, and shutdown corrections. Inspected
identity is now
`sha256:205fa464fc25820d659bfcf3cc11748e0f96527dca4fa9c012d5d1bf3079dfc5`,
linux/amd64, 516,723,659 bytes (approximately 493 MiB), configured user appuser.
Dependency installation and protobuf generation completed. The initial image
record above remains historical evidence. No RPC runtime tests, container start,
or replacement of the running candidate accompanied this rebuild.

This overlay reuses the existing server, API-key interceptor, scope checks,
health, and reflection implementation. It does not certify their runtime
correctness. The private candidate uses the server's existing insecure transport
path; exposing it beyond this network needs a reviewed TLS arrangement and
matching health/client configuration. No certificate mounts or public ingress
have been introduced.

Source review found a concrete database interface mismatch in the legacy
transport: `_get_db_pool` returns raw psycopg2 connections while authentication
and several handlers call `.execute`, `.text`, and `.mappings` on the shared
connection interface. The subsequent [pooled database adapter](grpc-database.md)
corrects that mismatch in source; the first image predates this correction.
The later [authentication correction](grpc-authentication.md) binds context
during execution and fixes scope parsing in source. Runtime transaction,
context, and permission checks remain separate acceptance concerns; rebuild
the image before adoption.

Before profile adoption, build the target on AMD64 and ARM64; confirm generated
protobuf imports and registration of both business services; exercise permitted,
missing, expired, and insufficient-scope credentials; compare approved reads
with native API/CLI results; verify database failure and shutdown behavior.
Preserve credit custody, governance, and human confirmation boundaries on write
methods. Check authentication context propagation and scope parsing against
actual handlers before claiming parity. Minimal/edge deployments do not need
this transport to operate.

The recorded image digests below are historical builds. They were built before
the latest checkout and are not release artifacts; rebuild the target from the
reviewed source before any deployment. The optional gRPC service has not been
started, and no RPC has been issued against the active candidate.

## Rollback

Stop/remove only the optional grpc service and omit this overlay from subsequent
candidate commands. Retain the database and named volumes. Removing an overlay
from a command does not automatically stop an already-running orphan service;
stop it explicitly. Revert the additive Docker stages if needed. No schema or
business data migration is associated with transport installation.
