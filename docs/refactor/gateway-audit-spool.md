# Gateway audit outage journal

Updated: 11 October 2026. This is a bounded recovery layer for failed writes to
the canonical PostgreSQL `access_audit_log`; PostgreSQL remains the authoritative
audit store. No database migration or new Python package is required.

## Write and replay contract

`GatewayAudit.log` assigns each event a UUID and timezone-aware occurrence time
before attempting PostgreSQL. It writes the UUID to `access_audit_log.id` and
the original occurrence time to `created_at`. If PostgreSQL write fails, the
same event is serialized into the local SQLite journal. A retry uses the same
UUID; the PostgreSQL insert uses `ON CONFLICT (id) DO NOTHING`, so a commit
whose acknowledgement was lost does not create a duplicate audit row.

Replay runs in two places: a request first attempts to drain earlier events,
then writes its current event; and the FastAPI lifespan worker replays batches
of 100 immediately at startup and every 15 seconds. The middleware offloads
synchronous audit I/O to the thread pool. Events are replayed in journal order
and removed only after the PostgreSQL audit insert commits.

## Journal bounds and configuration

- `KOKONUT_GATEWAY_AUDIT_SPOOL_PATH` selects the SQLite file. Without it, the
  path is `$XDG_STATE_HOME/kokonut/gateway-audit.sqlite3`, falling back to
  `~/.local/state/kokonut/gateway-audit.sqlite3`.
- `KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS` sets the maximum pending records;
  the default is 10,000. Compose uses this default and permits an override.
- `KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD` sets the pending-event count
  that raises a capture alert and restricts mutating routes. `0` selects the
  default: 80% of the configured queue cap, rounded up.
- A serialized record is limited to 16 KiB. Gateway fields are bounded before
  serialization.
- SQLite uses WAL mode, `synchronous=FULL`, and a 5-second busy timeout. WAL
  and schema initialization use up to eight attempts for transient busy/locked
  errors with capped exponential backoff for concurrent first writers. The
  journal directory must be owned by the process and have no group/world
  permissions; the database file is created with mode 0600.
- Candidate and portability Compose manifests mount named volumes at
  `/var/lib/kokonut/gateway-audit`. The kernel image prepares that directory
  with mode 0700 for its application user.

The journal contains the same request metadata as the canonical audit row and
is plaintext. Protect the volume using host/storage encryption and access
controls appropriate for audit data. Do not put one SQLite journal on a
multi-host network filesystem. This is a local single-deployment durability
layer, not a distributed queue.

After gateway policy processing and before a non-read route invokes its
handler, the gateway tries to replay queued events, checks the journal count,
and commits/removes a small transactional write probe on the journal. It also
reserves threshold headroom in SQLite and holds that reservation through
handler execution and audit capture. `BEGIN IMMEDIATE` serializes admission
across local gateway worker processes sharing the same journal file. Each
worker holds a private POSIX advisory lock while it has reservations; the next
admission reaps rows whose owner lock is gone after a worker exits. The current
gateway CLI starts one Uvicorn worker, but custom local workers sharing one
POSIX journal use the same guard. Multi-host filesystems, independently mounted
replicas and replica failover are not accepted. The guard returns 503 with
`Retry-After: 30` when local journal storage is unavailable or the queue plus
active reservations reaches its alert threshold. Requests already past
preflight can still finish if storage fails afterward, and concurrent read or
denial audit events can consume headroom. Reads remain available. `/health`
includes an `audit_capture` value of `ok`, `degraded`, or `unavailable`; its
degraded state considers queued events and active reservations. The maintenance
CLI reports persisted count, active reservation count, threshold and
restriction state; abandoned rows can appear until the next write preflight
reaps them. Reservation sidecars contain only an owner UUID and use mode 0600.
A failed release in a live worker is also reaped on the next preflight. The
transition to degraded/unavailable is logged once per app process.
Individual requests rejected by this guard are not added to the already-stressed
journal; monitor the health field and application error logs.

## Operator checks and checkpoint recovery

The maintenance CLI reports counts and integrity metadata only; it never
prints audit rows. The portability app image has been rebuilt with the CLI, and
the unified command was invoked in a temporary network-disabled container with
no database or journal volume mounted. Checkpoint, verify, restore and
no-overwrite behavior also passed in that image against a private temporary bind
fixture. Existing portability app/worker containers remain stopped on their
earlier image; the candidate was untouched.
Rebuild and recreate a service when you want the command available in that
running container. Then run it in the app image so it sees the configured
journal path and volume:

```sh
python3 -m services.cli audit-spool status
python3 -m services.cli audit-spool verify --path /var/lib/kokonut/gateway-audit/gateway-audit.sqlite3
```

For a planned checkpoint, create a new private directory on a separate
checkpoint destination, then ask SQLite to create a consistent snapshot. The
destination must be a new file inside a directory owned by the current user
with mode 0700. The utility uses SQLite's online backup API, verifies integrity
and event identity, writes mode 0600, and refuses to overwrite an existing
file:

```sh
mkdir -m 700 /tmp/kokonut-audit-checkpoint
python3 -m services.cli audit-spool checkpoint \
  --destination /tmp/kokonut-audit-checkpoint/gateway-audit.sqlite3
python3 -m services.cli audit-spool verify \
  --path /tmp/kokonut-audit-checkpoint/gateway-audit.sqlite3
```

Copy the verified file to a private host checkpoint location and encrypt it
before long-term retention or transfer (for example, with the approved `age`
recipient). Delete the temporary plaintext only after the encrypted copy has
been checksum-verified. The SQLite file contains audit metadata, so do not
place it in a broadly readable directory or an unencrypted general backup.

To restore, decrypt a checkpoint into a private staging directory, verify it,
and restore it to a new path on the journal volume:

```sh
python3 -m services.cli audit-spool verify --path /restore/gateway-audit.sqlite3
python3 -m services.cli audit-spool restore \
  --source /restore/gateway-audit.sqlite3 \
  --destination /var/lib/kokonut/gateway-audit/recovered.sqlite3
```

The command never installs over the configured journal. Before an operator
replaces that file, stop every API/worker process using the volume, preserve a
copy of the current volume, and confirm the recovered file's integrity, owner,
and mode. Then install it at the configured path and start one API process;
check `status` and logs for replay progress before restoring normal traffic.
After PostgreSQL is healthy, replay drains records in batches of 100. Retain
the encrypted checkpoint until the queue reaches zero and database audit counts
have been reconciled. The spool is a delivery queue, not the long-term audit
archive; PostgreSQL retention remains a separate policy.

At the configured threshold, the gateway logs a capture alert and blocks new
mutating routes while retaining headroom for in-flight work and non-write audit
events. Restore PostgreSQL and free or expand the dedicated volume promptly.
Preserve the spool and do not raise the cap blindly. Reads and requests already
past preflight can still produce audit events, so the hard queue bound remains
the final protection against unbounded storage growth.

## Remaining acceptance gaps

The journal survives application-container replacement only while its mounted
volume survives. It does not protect against host loss, volume deletion or
corruption. If the journal is full, an event is too large, permissions are
unsafe, or SQLite fails, the failure is logged. The gateway blocks new
mutations after preflight detects unavailable storage or queue saturation, while
read-only routes remain available. Therefore it does not promise complete audit
capture during an extended outage or storage failure. It cannot detect an empty replacement volume after process
restart without an external volume-health signal, and a storage failure after
preflight can affect an in-flight operation. A production alert destination,
approved retention schedule and operational owner are still required.

The volume must be retained during rollback until its pending count is known to
be zero or its contents have been exported/recovered. Reverting application
code alone does not drain a journal created by this implementation. Do not
delete a spool volume as routine cleanup. A future multi-replica deployment
needs a separately reviewed ownership and failover design; this local SQLite
path does not certify scale or cross-host replay.

## Verification and status

The isolated real-ASGI recovery probe stopped PostgreSQL, sent a request through
the actual middleware, observed the expected 503 with `Retry-After: 30`, and
confirmed one audit event in the journal. After replacing the API container
while retaining the same named volume and restoring PostgreSQL, the FastAPI
startup worker replayed exactly one row without another request. The original
`created_at` was retained, duplicate-ID count was one, and the journal drained
to zero. The exact probe, image identity, cleanup and limits are in the
[sanitized recovery record](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).
The maintenance CLI image identity and no-volume runtime probe are recorded
separately in the [CLI image check](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).

This is partial CAP-040 evidence. Cold initialization with 12 concurrent
writers passed three times after adding bounded retries for transient WAL/schema
lock races. Ten warm writers committed 201 events, including a seed event. A
separate live-write checkpoint captured a valid 166-event snapshot while all
eight writers were still active, and the source later finished with 481 events.
[Contention evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json).
This is process-level local-filesystem evidence, not a power-loss or storage-device
failure test. Physical-device/power failure, installation of a restored copy into a stopped Compose volume,
candidate-provider activation, replica failover/scale, and production ingress
remain acceptance gates. Process-exit, online backup, and new-path restore
behavior are separately exercised in the [checkpoint rehearsal](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).
The probe removed its one synthetic audit row,
temporary application containers and temporary volume, stopped the portability
database to its previous state, and did not touch the active candidate.
