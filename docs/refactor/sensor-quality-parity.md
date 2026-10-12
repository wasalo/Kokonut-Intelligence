# MQTT reading quality and payload dimensions

MQTT now passes the signed payload's `quality` field (default `good`) to the
shared sensor validator, matching HTTP's quality input. `bad` and `suspect`
readings produce the existing suspect stored quality; unknown quality values
are rejected. Existing range/missing-unit warnings can also mark a reading
suspect. Raw signed evidence retains the original quality and is not rewritten.
No verification or publication authority is added by this normalization.

Before database lookup, MQTT now rejects non-string/empty/oversized device IDs,
non-string/oversized units or timestamps, non-string/oversized quality, and
non-string signatures. Dimensions match HTTP's device/unit/timestamp/quality
limits. The reading handler also rejects payloads exceeding 10 KiB, including
legacy delivery and direct operator replay paths. These are explicit changes
to accepted MQTT input; review publishers before adoption.

MQTT still uses its existing topic-bound canonical HMAC format, while HTTP
signs exact body bytes. Timestamp mode, active-device checks, source/outbox
transactions, and existing duplicate keys remain unchanged by this slice.
This is one parity correction, not a shared domain-service extraction or proof
that every transport behavior is equivalent. Durable QoS 1 receipt persistence
retains its separate size guard before processing oversized broker payloads.

Static lint and diff checks passed. No tests, messages, replay operations,
database writes, images, or containers were changed. Pending acceptance includes
every quality value, quality omitted/null/structured, malformed fields, signed
quality tampering, body boundaries, suspect/out-of-range readings, HTTP/MQTT
comparison, and terminal-rejection receipt/ACK behavior. Rebuild before use.

Rollback preserves evidence and stored quality. A previous image ignores MQTT
quality again; pause ingestion before selecting a validated alternative. Do not
rewrite already committed quality or lifecycle states to simulate parity.
