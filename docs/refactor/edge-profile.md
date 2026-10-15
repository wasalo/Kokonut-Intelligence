# Edge candidate profile

Combine `docker-compose.kernel-edge.yml` with the standalone candidate file.
Use a separate project (`kokonut-kernel-edge`) for a separate device/database,
or the existing candidate project only when deliberately changing that
candidate's configuration. Never use the legacy project name.

    docker compose -p kokonut-kernel-edge -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-edge.yml build app

The overlay selects encrypted local private media and creates a dedicated
`kernel-private-media` volume. The image prepares its mount point owned by UID
10001 with mode 0700 so a newly created named volume receives private directory
permissions. Existing volumes must already satisfy those ownership/permissions;
the runtime never relaxes them. The encryption key is mandatory only for this
overlay and must be supplied through encrypted secrets. Never embed it in YAML.

Database and app each have a 1 GiB memory limit and a two-CPU cap. PostgreSQL
uses 40 connections, 128 MB shared buffers, 4 MB work memory, and 64 MB
maintenance work memory. These are starting limits, not measured guarantees.
Work memory applies per query operation; the container limit is still the hard
boundary. Memory exhaustion may terminate processes; durable recovery and
workload admission must be exercised before adoption.

The intended hardware target is ARM64 Raspberry Pi with at least 4 GB RAM and
SSD storage, allowing OS/file cache headroom beyond container limits. No
architecture is forced by this overlay. Confirm both base-image manifests and
selected Python wheels support ARM64, build on that platform, and measure
normal/peak resources, sustained writes, restart behavior, and restore on actual
hardware. AMD64 candidate startup does not certify a Pi deployment.

The base database digest is AMD64-only. The profile planner now selects a
custom ARM64 PostGIS image and separate Compose project for edge ARM64; see the
[current profile record](arm64-database.md). Prior QEMU acceptance covers the
minimal app/database through migration 386 only. Current schema sources through
migration 400 need a fresh code-only ARM64/QEMU replay, and no physical Pi behavior is
claimed.

Public PostgreSQL reads, API auth, offline sync, durable workers, and optional
Web3 libraries remain present. Remote blockchain/RPC connectivity is still
external. ML/GIS jobs requiring omitted packages must not be scheduled on this
image until routed to suitable workers or separately supported. Private media
uploads need no object-store service; cloud S3 remains available in other profiles.

## Adoption gates and rollback

- Resolve fresh database schema/seeds and only register reviewed runnable jobs.
- Load a distinct random media key through SOPS; back up it and encrypted media.
- Validate directory ownership, upload/sync, evidence hashes, disk-full behavior,
  interruption/recovery, and restoration together with the PostgreSQL snapshot.
- Measure the 4 GB device under realistic concurrency and 24-hour operation.
- Keep the API localhost-only unless a deliberate authenticated TLS ingress is
  configured. This overlay inherits the base's private database networking.

Merged Compose validation and whitespace checks passed. No edge image/volume,
encryption key, or device deployment was created. Runtime/security/ARM64 checks
remain pending. The currently running candidate is unchanged.

Rollback removes the edge overlay and explicitly rebuilds/recreates only the
app as appropriate. Preserve media volumes and their key. Switching an existing
installation back to S3 requires object migration/per-object routing first;
changing the global setting alone cannot preserve reads of local objects.
