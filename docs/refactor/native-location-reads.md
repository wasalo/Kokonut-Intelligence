# Native public location reads

## Current execution boundary

Location list/detail handlers now offload synchronous PostgreSQL reads and
Directus HTTP calls through Starlette's thread pool. The native default connection
uses a 3-second connection timeout, a read-only transaction, a 5-second statement
timeout, and a 2-second lock timeout. Cursor cleanup is followed by explicit
rollback and connection close, including query failures. Injected connection
factories retain their no-argument contract and control their connection setup.

These bounds cover individual database operations, not the entire HTTP request:
thread-pool queueing, connection/DNS behavior, cleanup, serialization, and the
existing Directus HTTP retry policy can add time. Offloading prevents these
synchronous operations from directly occupying the async event loop; it does not
provide a new admission limit, connection pool, or concurrency certification.
No route policy, fields, visibility, ordering, or response envelope changed.

This source edit passed lint/static checks and was subsequently rebuilt/deployed
to the isolated AMD64 portability API; see its runtime record. The candidate
image remains unchanged. No tests or live route requests ran in this slice.
Earlier deployment statements below describe the initial native-read implementation.

When Directus is disabled, the existing gateway location list/detail routes now
read PostgreSQL through `services/gateway/locations.py:public_locations`. When
Directus is enabled, existing proxy behavior is retained. No route policy or
public-access declaration changes.

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

Lint, provider-boundary, and whitespace checks passed. Runtime visibility,
invalid-ID, response-contract, and auth checks remain pending. The candidate
image has now been rebuilt/restarted with this source edit.
No live location requests or private
data queries were made during implementation.

Rollback: revert the two native branches and retain the Directus proxy code.
No schema or data rollback is required. A disabled Directus deployment would
then lose these reads until its provider is restored.
