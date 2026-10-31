# Batch 2 — active-work and private-media recovery preparation

10 October 2026. Fixture specification and operator commands prepared. No fixture
records, keys, uploads or jobs were created. No acceptance suites or media commands
were executed; Ruff passed for both new scripts. Existing deployments unchanged.

Set `SOPS_AGE_KEY_FILE` to the private age identity path before running recovery
commands; keep the identity outside the repository and share only its public
recipient when encryption requires one.

## Operator commands

scripts/kernel-media-checkpoint.py archives existing encrypted LocalMediaStore
objects, without decrypting them, under an additional age envelope. It requires
an absolute owner-controlled 0700 directory, private regular objects, immutable
hashed .bin filenames and KKM1 envelopes. Symlinks/unexpected/incomplete files fail.
Capture checks object changes and directory membership; it never overwrites a
checkpoint. A scoped database archive SHA256 and custody label bind the manifest.

Quiesce uploads, deletion/expiry and database writes first. Capture the database
with kernel-checkpoint.sh while quiesced. Then, as the media directory's owner:

```bash
python3 scripts/kernel-media-checkpoint.py \
  --directory /ABSOLUTE/PRIVATE_MEDIA \
  --destination backups/NEW_MEDIA_CHECKPOINT \
  --database-checkpoint backups/DB_CHECKPOINT/manifest.json \
  --key-reference sops:MOBILE_MEDIA_LOCAL_KEY \
  --recipient AGE_PUBLIC_RECIPIENT --quiesced
```

The operator confirmation is not an enforced distributed lock. Quiescence is
mandatory to coordinate database references and object deletion. The key-reference
is a label, not the key: preserve the original 32-byte local-media key separately
inside encrypted secret custody, with the age decryption identity separately.
The media and outer age keys serve different purposes and neither may be lost.
The running portability environment has no configured local-media key or volume;
do not invent a production upload backup from its empty filesystem.

scripts/kernel-media-restore.py checks ciphertext hash and size, strict flat member
names, regular-file types, duplicates, expected sizes and object hashes. It writes
to a new 0700 staging directory and drains age to EOF before finalizing; failures
retain staging privately. It creates a new destination exclusively and links files
without overwriting existing objects. Do not connect the destination to an app
until the complete restore and reference checks finish. If final linking fails,
retain both partial directories; no automatic cleanup/pruning is performed.

```bash
python3 scripts/kernel-media-restore.py \
  --checkpoint backups/MEDIA_CHECKPOINT \
  --identity "$SOPS_AGE_KEY_FILE" \
  --destination /ABSOLUTE/NEW_RECOVERED_MEDIA
```

Restore PostgreSQL separately. Match its archive SHA256 against
database_archive_sha256 in the media manifest; retrieve the referenced media key
from secret custody. For every restored mobile_media_upload.object_key, verify
the expected hashed filename and call LocalMediaStore.head_private with the original
object key/key material. That authenticates AES-GCM including associated data;
compare ContentLength with DB size_bytes. Outer tar/hash success does not prove
this key/reference check. Object completeness, orphan retention policy and device
scope need their own evidence. Ciphertext filenames are preserved, not object IDs.

## Exact isolated fixture specification

Use a NEW current-schema recovery database restored from the portability checkpoint
(364 schemas through 373), plus a new local-media directory. No existing recovery
DB or running portability stack receives these records. Use Kokonut Adelphi only;
record fixture provenance explicitly, without broad seed-pilot.sh or live credentials.

| Fixture | State to preserve | Acceptance evidence required |
| --- | --- | --- |
| One disabled scheduled_task | Known registry JobSpec, fixed argv, no overlap, same_window, retry_attempt 1, retry_at, run_window_at | Exact task/schedule/window and retry state survives restore; no implicit enablement |
| One running task_run | Matching task/worker/lease_token, attempt_count, heartbeat_at, scheduled_for; expired task lease | Ownership-aware stale-run recovery; former worker cannot complete after lease loss |
| One completed task_run for a distinct window | Completion timestamp and scheduled_for | Dependency completion for one window does not unlock another |
| One processing platform_event | Original UUID, payload, bounded retries, expired lease/owner | Reclaim with same event identity; preserve completed handler delivery without rerunning its effect |
| Two handler deliveries | One success, one error, each with attempt_count and history | Successful handler remains skipped; failed handler alone retries within budget |
| One dead letter | Pending disposition and failure history | Replay/disposal requires explicit operator identity/reason and retained history |
| One device-scoped offline collection | Adelphi location and enrolled synthetic device, fixed client_id | Restored attachment remains bound to the same device/farm/client identity |
| One uploaded and one attached media row/object | Non-private sample JPEGs, recorded hashes/sizes, expiry; attached_collection_id consistent with status | Correct-key AES authentication and DB/object completeness; wrong key and device/farm substitution rejected |

Relevant schemas: 116, 117, 139, 164, 165, 337 (lease ownership), 344 (device
tokens), 358 (private media), 371 (run windows). Owner modules:
services/scheduler/engine.py, services/events/, services/mobile/api.py,
services/mobile/local_media.py. Preserve lifecycle review boundaries for any domain
records; these recovery rows do not confer verification/publication authority.

## Execution sequence and gates

1. Prepare reviewed fixture records/identities and controlled handler effects.
   Keep schedules/handlers disabled while constructing the isolated fixture.
2. Record DB state, leases/windows, handler effects, file hashes and secret custody.
3. Quiesce; capture database/media checkpoints; create matching development mirror.
4. Restore to another fresh DB/media pair without workers or application access.
5. Compare durable state and authenticate references/objects using the original key.
6. With explicit verification authorization, exercise bounded recovery, stale-owner
   rejection, idempotent handler effects, replay/disposal and media/device policy.
7. Stop isolated roles, retain evidence/ciphertext and update affected capability gates.

No gate above is closed merely by preparing these scripts/specifications. Rollback:
running services unchanged; fixtures remain on isolated volumes, with originals
and encrypted archives retained. Independent production R2 backups remain deferred.

### Batch 2 event recovery exercised — 10 October 2026

After the host restart, started only the retained private recovery fixture for
this slice. Host project/image/volume/network/schema guard passed. Eight synthetic
event checks passed against real PostgreSQL: expired lease reclaim/stale owner
rejection; successful delivery skipped on retry; bounded retries to dead letter;
audited replay with duplicate rejection and successful-delivery preservation;
orphan replay rejection; operator identity/reason requirements; audited disposal
with duplicate rejection. Handler invocation used controlled outcomes; no domain
handler or external effect ran. Synthetic handlers disabled again on exit.

[Evidence](builds/2026-10-10-recovery/fixture-events.json).
Reproducible guarded launcher: `bash scripts/kernel-recovery-event-checks.sh`
after loading encrypted secrets and starting the fixture. This mutates the exact
seeded event fixture and is intentionally not repeatable against completed state:
restore the retained pre-exercise checkpoint into a separately reviewed fresh
fixture before another run. Never rerun its seed into existing work tables.
The first attempt stopped before claiming work because a check assumed no standard
handler registrations; corrected to inspect the synthetic event type only.

Fixture stopped afterward; volumes/backups retained. Legacy stack remains stopped.
Candidate services restarted automatically; portability services remain stopped
following the host restart. No deployment promotion occurred.
Actual handler side effects/idempotency, child-process timeouts, concurrent workers,
roles/grants and provider ownership still require evidence. Batch 2 remains active;
no capability becomes fully accepted.
