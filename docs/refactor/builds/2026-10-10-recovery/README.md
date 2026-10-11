# Batch 2 scoped recovery evidence

10 October 2026. Encrypted age checkpoint of portability PostgreSQL restored into
an empty isolated database with pg_restore --single-transaction --exit-on-error.
Ciphertext SHA256 matched before decryption. No plaintext dump was written to disk.
Source and restored migration inventory digests, extension versions and selected
aggregate counts match: see evidence.json. Source/image identities are retained.
The source checkpoint manifest remains its immutable creation-time record; its
restore_rehearsed=false describes creation time. The separate evidence records
subsequent successful restore (exit 0).

All eight selected workload/media tables are empty. No active lease recovery,
payload parity, authorization/grant parity or complete legacy restore is certified.
Roles/grants, Metabase DB, external media and remaining legacy stores are excluded.
No test suites ran. An early aggregate query during the open restore transaction
could not see schema_migration; the comparison was repeated after successful commit.

Encrypted Redis/broker persistence archive was also created with readonly mounts
of the stopped legacy volumes, no network. See provider-archive.json for scope/hash.
Archive restore and logical message/session inventory remain open. Neither service
was started and their original volumes remain attached and unchanged.

Recovery container is stopped; its dedicated volume is retained. No API/worker
started in recovery. Existing source deployment remains running. Rollback is the
unchanged source deployment; do not prune checkpoint or recovery volumes. Archives
are under ignored backups/kernel-batch2-20261010 and contain private data. Only
aggregate metadata is kept here; a second independent encrypted copy is still due.

### Batch 2 exercised synthetic recovery — 10 October 2026

With explicit user authorization, provisioned the private fixture and restored
364 checksummed schema records. Applied disabled work and two authenticated
synthetic media records. Captured a quiesced paired encrypted DB/media checkpoint;
restored DB into fresh `recovery_roundtrip` and media into an unused private directory.
All 12 selected whole-row count/fingerprints match. Both restored objects authenticate
with the separately age-encrypted development AES key. Wrong key, changed associated
data, duplicate work/media seeds, reused restore destination and capture without
quiescence were rejected. Actual scheduler code recovered the expired lease,
retained its original window, advanced retry to 2 and rejected stale completion;
no job dispatched. Fixture stopped after checks; volumes and checkpoints retained.

[Sanitized results](fixture-roundtrip.json).
Backups/key custody: ignored `backups/recovery-fixture-20261010/`; the key itself
is only persisted as `media-key.age`. This is a local development recovery exercise.
Live enrollment/consent, handler effects/replay/disposal, role/grant policy,
external provider ownership, production/Pi certification and full recovery acceptance
remain open. Batch 2 stays active; no capability is fully accepted.
