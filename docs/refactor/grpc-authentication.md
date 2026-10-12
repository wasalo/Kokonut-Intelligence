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

## Compatibility and acceptance

Review existing API-key scope records before transport adoption. Keys relying on
the old incorrect first-two-component interpretation need deliberately reviewed
scope changes; do not automatically broaden their grants. The baseline focused
scope test using `ecocredit:class:read` to authorize `ecocredit`/`class` describes
the old bug and will need updating when runtime verification is authorized.
No tests were added, changed, or run in this slice.

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
