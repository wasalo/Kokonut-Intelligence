# gRPC authentication context and scope matching

## Source corrections

The API-key interceptor formerly set and reset context around handler discovery.
The reset occurred before the business handler executed. It now wraps the
resolved RpcMethodHandler and sets identity during invocation instead. Unary
calls reset their context in finally; streaming responses retain identity
through iteration and reset on completion, error, or generator close.

The wrapper preserves request/response streaming cardinality and the original
deserializer/serializer for all four RPC shapes, using the public
[gRPC handler constructors and interceptor contract](https://grpc.github.io/grpc/python/grpc.html).
Unknown handlers still return None. Key lookup, active/expiration checks,
existing health/reflection exemptions, and business-method scope requirements
remain in their existing paths. No credential or role is provisioned.

Scope strings now split at the last colon. `ecocredit:class:read` grants resource
`ecocredit:class` action `read`; it does not grant resource `ecocredit` action
`class`. Exact resource/action matches and explicit `*:read`, `resource:*`, and
`*:*` patterns remain supported. Bare resource strings, missing components,
nonstrings, and malformed scope containers grant nothing. There is no prefix
matching or inference of parent-resource permissions.

## Location-scoped credit writes

Credit-batch creation and class enrollment now require exact
`resource:action:location-uuid` entries in the database API-key record:
`ecocredit_batch:create:<uuid>` and `ecocredit_enrollment:apply:<uuid>`.
The interceptor carries only the SHA-256 key hash—not the submitted key—into
handler context. Each RPC checks the exact scope before acquiring its write
connection, then calls the existing
`kokonut_security.set_gateway_tenant_context` through
`set_gateway_tenant_context()` on that same non-autocommit connection before
calling the domain writer. PostgreSQL rechecks credential status, expiry,
scope, active location, and current verified owner and signs transaction-local
context. Legacy global scopes and wildcards no longer authorize these two
operations.

This is the first scoped credit-write slice. The remaining credit-class
mutation RPCs still need an equivalent location/account contract or a separate
administrative boundary. Their existing paths and the broad credit-class table
grants are not changed here; this slice does not close C1 or establish table-
level tenant isolation.

## Compatibility and acceptance

Review existing API-key scope records before transport adoption. Keys relying on
the old incorrect first-two-component interpretation need deliberately reviewed
scope changes; do not automatically broaden their grants. The scope regression
accepts `ecocredit:class:read` only for resource `ecocredit:class` and rejects it
for the shorter resource `ecocredit`. The new scoped-write selection also
verifies exact location grants, same-transaction context setup, and old global
scope denial; 13 focused mock tests pass. The CreateBatch loopback acceptance
passes with a synthetic key and fake database/domain writer.

Pending runtime checks: identity visible in actual unary and streaming handlers,
serializer/cardinality preservation, reset after success, exception, abort,
cancellation, and stream exhaustion; concurrent caller isolation; key lookup
failures; exact and wildcard grants; colon-bearing resources; malformed and
insufficient scopes; unknown methods and exemption behavior. Long-running
streams still use identity resolved at connection setup; mid-stream revocation
or expiration revalidation is not introduced by this correction.

Static lint, provider boundaries, dependency grouping, and diff checks passed.
The optional image must be rebuilt to include this change and the preceding
database adapter. No service was started, credentials changed, or RPC executed.

## Rollback

Keep the optional transport stopped if these corrections need reverting.
Reverting restores the baseline context and scope bugs and is not a functioning
authorization recovery. No business state or schema rollback is needed. Domain
write custody and independent human confirmation still require separate parity
review before transport deployment.
