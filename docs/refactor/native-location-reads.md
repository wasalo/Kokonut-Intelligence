# Native public location reads

## Current execution boundary

All public location list/detail handlers now offload synchronous PostgreSQL
reads through Starlette's thread pool. They no longer proxy public requests to
Directus when that optional provider is enabled. The native default connection
uses a 3-second connection timeout, a read-only transaction, a 5-second statement
timeout, and a 2-second lock timeout. Cursor cleanup is followed by explicit
rollback and connection close, including query failures. Injected connection
factories retain their no-argument contract and control their connection setup.

These bounds cover individual database operations, not the entire HTTP request:
thread-pool queueing, connection/DNS behavior, cleanup, serialization, and the
cleanup, serialization, and connection behavior can add time. Offloading
prevents synchronous database operations from directly occupying the async
event loop; it does not provide a new admission limit, connection pool, or
concurrency certification. Route policy, public visibility, ordering, and the
legacy response wrapper remain unchanged. Directus-enabled deployments now use
the same five-field projection as the native path.

Three focused HTTP checks cover provider-independent dispatch, the stable legacy
wrapper, and detail validation/not-found behavior. No live route request was
made in this slice.

The unversioned Gateway location list/detail routes always read PostgreSQL
through `services/gateway/locations.py:public_locations`, regardless of the
Directus feature flag. The public field set is explicitly limited to ID, name,
country, region, and status. Directus remains available for its administrative
and other compatibility surfaces; it no longer backs these public Gateway
routes.

The native path uses `v_public_farm_summary` from migration #018 rather than
reading raw location rows. That view requires active location status and a
verified/published farm registry record. Public fields are explicitly limited
to id, name, country, region, and status. Metadata, precise geometry/coordinates,
financial baselines, and ownership information are not selected. No governed
record is created or lifecycle state changed.

List results are bounded to 100 and ordered by name then ID. Detail retains UUID
validation and returns 404 for nonexistent or unpublished locations without
revealing which condition caused exclusion. The current gateway's outer `data`
field contains serialized upstream JSON; the native path retains that envelope
shape, including the inner `data` array/object. Normalizing this legacy double
JSON encoding is a separate versioned API change.

This is a conservative public projection, not certified Directus field parity.
It does not implement authenticated full-location access or generic CRUD. Live
Directus policy fields still need comparison before declaring parity; the legacy
stack stays stopped. Native read-only connections/cursors close on failure.

Candidate/populated response parity remains pending. Rollback by selecting the
preceding Gateway image; that restores provider-dependent behavior and should
only be done after Directus public permissions and field visibility are
verified. No schema or data rollback is required.
