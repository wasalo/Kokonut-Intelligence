# Audited ClickHouse outbox operator actions

Migration 374 adds `clickhouse_outbox_operator_audit`. Apply through the checksummed
migration runner before using the updated service; historical migrations unchanged.
Replay now requires actor and reason; previous two-argument Python callers must
supply both. Disposal is new and accepts resolved/discarded only.

```sh
python3 -m services.ingestion.clickhouse_outbox --replay-dead-letter ROW_UUID --actor OPERATOR --reason "Reviewed source and delivery failure"
python3 -m services.ingestion.clickhouse_outbox --dispose-dead-letter ROW_UUID --disposition discarded --actor OPERATOR --reason "Reviewed duplicate projection"
```

Actions require a dead-lettered row, lock it, transition and insert the audit in
one database statement/transaction. Records retain action, actor, reason, previous
attempt count and payload hash. Replay resets attempts; disposal retains them.
Source/projection payloads remain intact. Duplicate actions return an error and
CLI exits nonzero. Missing/blank actor/reason and excessive lengths fail validation.
Actor is an operator-supplied label, not authenticated identity proof; a future
API must derive identity from its trusted authorization context.

[Isolated checks](builds/2026-10-10-recovery/fixture-outbox-audit.json): required
identity/reason bounds, replay and both dispositions audited exactly once,
attempt history/payload preservation, forced audit insert failure rolling back
transition. Test-only trigger was removed; no domain handler/sink invocation.

Only the retained recovery fixture was migrated: 365 schema files through 374.
Candidate/portability images and databases have not been promoted or rebuilt.
Deployment requires coordinated new source + migration; reverting to older code
would remove audit enforcement and is not an acceptable normal operator rollback.
If rollback is needed, stop delivery/operator actions, retain audit records and
use reviewed recovery. Never drop this table to roll back or edit applied schema.
Runtime DB roles currently permit broad access; restricting direct audit mutation,
authenticated operator authorization, concurrent replay tests and sink crash
reconciliation remain open. This is database atomicity evidence, not tamper-proof
or complete analytics acceptance.
