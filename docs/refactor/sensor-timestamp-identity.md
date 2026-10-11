# Shared HTTP/MQTT timestamp identity

`field_validation.parse_transport_timestamp` now supplies both HTTP and MQTT
timestamp parsing. `KOKONUT_SENSOR_TIMESTAMP_MODE` defaults to `legacy`, retaining
existing local-clock insertion and optional server-time behavior. Explicit `utc`
requires a supplied ISO datetime with a timezone and converts it to UTC before
date/time columns, validation dedupe keys, and projection timestamps are derived.
MQTT QoS 1 retains its existing independent requirement for a stable timestamp.

Equivalent offset representations therefore use the same UTC clock fields in
UTC mode. Exact request-body/payload signatures and raw evidence are preserved;
the helper never rewrites signed input. This does not add a request idempotency
key, compare conflicting duplicate values, or change the existing unique key.
CSV/date-time parsing remains unchanged. Invalid timestamp modes fail parsing;
configure only the documented values before starting ingestion.

## Adoption boundary

No Compose profile selects UTC mode by default and no historical rows were modified.
Stop ingestion and review existing reading_date/reading_time values, source_raw
timestamps, timezone provenance, duplicate collisions, and outbox lineage before
switching. Naive historical timestamps cannot be assigned a timezone without
evidence. Plan any reconciliation as a separate reviewed migration/operation;
never rewrite an applied migration or delete readings to force parity.

Pass the same explicit mode to HTTP, MQTT, and operator replay environments.
The MQTT overlay now forwards the explicit environment setting with a legacy
default. Select UTC deliberately only after acceptance. Replay of retained naive or missing timestamps
can be rejected under the new policy. Review dead letters before changing it.

Static lint and diff checks passed. No tests, requests, replay operations,
database changes, image builds, or container changes occurred for this slice.
Pending acceptance: equivalent offsets across midnight, fractional seconds,
naive/missing/invalid input, stable retries, cross-transport duplicates, raw
signature preservation, timestamp precision in PostgreSQL/ClickHouse, conflicting
duplicates, and reconciliation of legacy timezone representations.

Rollback stops ingestion before restoring the prior mode/source. Preserve UTC
rows and evidence: reverting the parser does not convert already committed
timestamps and may reintroduce duplicate identities. Resume only after reviewing
mixed-history behavior. Timestamp normalization alone does not certify complete
HTTP/MQTT capability parity.

## Startup and replay configuration guard

Timestamp-mode validation is now separate from payload parsing. HTTP validates
and captures its mode before constructing the app. MQTT captures its setting
when constructing the subscriber and validates it before creating a broker
client, after the disabled-provider guard. It also checks configuration before
calling the durable receipt processor, so an invalid setting cannot become a
terminal payload rejection through that callback. Operator replay validates
the setting before reading/locking the receipt or resetting attempts; listing
and disposal remain available even when replay configuration is invalid.

The HTTP app and MQTT subscriber use their captured mode for their lifetime;
changing exported settings requires a restart. A malformed timestamp under a
valid mode still follows the existing payload-rejection/error contract.
The MQTT image built previously predates this guard and needs rebuilding before
adoption. Static lint, placeholder-only Compose parsing, and diff checks passed.
Startup/replay configuration failure and disabled-provider runtime checks remain
pending. No delivery evidence, attempts, or services were changed.
