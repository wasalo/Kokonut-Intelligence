# Isolated sensor-anomaly ML worker contract

Updated: 26 October 2026

## Purpose and boundary

The retained `anomaly_detector --ml-check` and `--ml-train` operations can run
through a narrow Kernel worker that does not inherit the shared application
database identity. This worker is separate from the event-driven
`sensor_anomaly_worker`: the latter processes signed events and can create
durable effects, while this worker only reads a selected location's sensor
time series and writes model artifacts to its private local volume.

The interface is `services.ingestion.sensor_anomaly_ml_worker.run_sensor_anomaly_ml(location_id, sensor_id=None, train=False)`.
It requires the default-off `isolated_sensor_anomaly_ml_worker` feature, a
canonical location UUID, and the exact worker identity
`sensor_anomaly_ml_source`. The worker establishes signed
`sensor_anomaly_ml/analyze` context and switches to
`kokonut_sensor_anomaly_ml_reader` in the same transaction before invoking the
existing ML implementation with `signed_source=True`. It always rolls back
and closes the connection, clearing transaction-local scope and role.

Migration `650_signed_sensor_anomaly_ml_source.sql` exposes one
security-barrier view, `kokonut_anomaly_ml_source.sensor_reading`. The view
requires the signed location scope, joins devices on both device and location,
and returns only `good` or `estimated` readings. The source login has no direct
table access, no direct view access, and only `SET` membership in the reader
role. The reader can select only the source view; its owner has only the
required source columns. If the source tables use RLS, the view owner is also
restricted by the signed location scope.

## CLI compatibility

With the feature disabled, existing manual behavior remains unchanged. With
the feature enabled, the CLI routes only `--ml-check` and `--ml-train` through
the isolated worker. They require one `--location-id`; `--all-locations` is
rejected before a connection opens. `--sensor` remains available to checks,
but not model training because the stored cache is location/type-scoped.
Baseline detection and the signed event-driven worker are not routed through
this read-only identity.

The default Kernel image does not install any of these ML dependencies. The
optional `ml-anomaly` Dockerfile target installs the five model requirements
from `requirements/ml-anomaly.txt` (pandas, NumPy, Prophet, scikit-learn, and
SciPy) plus `psycopg2-binary`, rather than inheriting the full Kernel image or
unrelated yfinance/gstools packages. The dependency-group checker verifies
that the model manifest remains an exact subset of `analytics.txt`. The
compatibility-range input is resolved into
`requirements/ml-anomaly-runtime.lock`, which pins every package and hashes
the supported Python 3.11 Linux AMD64 and ARM64 wheels. The ML Docker target
installs this lock with `--require-hashes` and binary wheels only. Regenerate it
with `scripts/compile-ml-anomaly-runtime-lock.sh`; the generator resolves
versions with pip-tools 7.6.2 and hashes only the wheels for those two target
architectures. A narrow CLI validates exactly one location and loads the ML
worker only after input validation. The `sensor-anomaly-ml` Compose profile is a one-shot worker, uses
a separate DSN and credential, and stores model artifacts in a dedicated named
volume. The Dockerfile resolves architecture-specific binary wheels in a
`BUILDPLATFORM` stage, then copies them into a standalone Python slim image.
Both AMD64 and ARM64 images build; network-disabled, read-only import smokes
and `pip check` pass for the worker and all five model packages ([build evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-builds.json);
[AMD64 smoke](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-native-smoke.json);
[ARM64 smoke](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-arm64-smoke.json)).
Docker reports 955 MB for AMD64 and 987 MB for ARM64, reductions of about 20%
from the preceding images. The root filesystems measured 702 MiB and 736 MiB
with `du`; these remain substantial opt-in images, not a size claim for the
default Kernel image. The checks establish software portability only and do not
verify performance, reliability, thermal behavior, or power-loss handling on a
physical Raspberry Pi. A synthetic 1,024-row, four-feature IsolationForest workload also passes under a 1 GiB memory limit and 2-CPU quota; the locked-image software smoke uses 188 MiB peak RSS on AMD64 and 325 MiB on ARM64/QEMU. This is not a hardware performance estimate ([locked build evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-hash-locked-image-builds.json)).

## Activation sequence

Activation is deliberately separate from source acceptance and requires a
reviewed rollout to the chosen database:

1. Apply migration 650 with the ordered migration runner after a fresh,
   restore-rehearsed checkpoint. This migration has **not** been applied to the
   candidate or legacy database as part of this batch.
2. Provision `KOKONUT_SENSOR_ANOMALY_ML_SOURCE_USER` and
   `KOKONUT_SENSOR_ANOMALY_ML_SOURCE_PASSWORD` through the runtime-role
   bootstrap after migration 650 exists. Keep the password, DSN, and worker
   credential in SOPS. The bootstrap validates that the login is distinct from
   the app and other worker roles, grants only database connect and reader-role
   `SET`, and removes stale schema/table/sequence privileges.
3. Provision a worker principal, a strong credential whose stored value is its
   SHA-256 digest, and exactly the intended location's
   `sensor_anomaly_ml/analyze` scope grant through an authorized operator path.
   This batch does not add an operator provisioning UI or seed any real grant.
4. Generate and inspect the selected Compose configuration before starting it:

   ```sh
   python3 scripts/kernel-profile.py standard --sensor-anomaly-ml --action config
   python3 scripts/kernel-profile.py standard --sensor-anomaly-ml --action build
   ```

   For ARM64 software targeting, add `--target-platform linux/arm64`. This
   includes the explicit ARM64 overlay; it is not hardware acceptance.
5. After the migration, login, scope grant, and secrets are verified, run one
   selected location at a time. Load the encrypted values into the environment
   and include the same base/profile manifests printed by the planner:

   ```sh
   source scripts/load-secrets.sh
   docker compose -p kokonut-kernel-candidate \
     -f docker-compose.kernel-candidate.yml \
     -f docker-compose.kernel-standard.yml \
     -f docker-compose.kernel-sensor-anomaly-ml.yml \
     run --rm sensor-anomaly-ml-worker \
     --ml-check --location-id LOCATION_UUID
   ```

   Model training uses `--ml-train --location-id LOCATION_UUID`. Never use
   `--all-locations` with this isolated identity.

The current disposable acceptance provisions synthetic identities only. No
real login, credential, worker grant, model artifact, candidate rollout, or
legacy service change has occurred.

## Verification and rollback

The focused unit selection covers feature-off and invalid-input failure before
database access, exact worker credential routing, signed scope before role
switch, source-view selection, model training source, and transaction cleanup.
The disposable PostgreSQL 16 runner applies and replays migrations 405, 419,
and 650; it verifies exact-location and quality filtering, context reset,
scope denial, direct-table denial, and the `SET`-only reader boundary. Its
fixture and evidence are synthetic and it removes its temporary container
before reporting success. See
[`check-sensor-anomaly-ml-source-disposable.py`](../../scripts/check-sensor-anomaly-ml-source-disposable.py)
and [the recorded result](builds/2026-10-26-recovery/sensor-anomaly-ml-source-disposable.json).

The current slim AMD64 image builds and a network-disabled, read-only smoke
imports the worker and all five model packages, confirms unrelated analytics
packages are absent, and has no database credentials. The slim ARM64 image
builds after cross-installing AArch64 wheels on the native build platform; its
network-disabled, read-only QEMU smoke reports `aarch64` and imports the same
worker and package set. See the three slim-image evidence files above. This
closes software image/import portability only. Physical Raspberry Pi
performance and reliability acceptance remain open.

Rollback is to leave the feature and Compose profile off, or disable the
profile and restore the previous CLI route. Preserve migration 650 and its
role/view definitions; do not drop them during application rollback because
that could invalidate an active or previously provisioned worker. Remove a
worker grant and revoke/rotate its credential through the approved operator
process if any were provisioned.

This closes source-owned, disposable-database, and software image/import
portability checks for the manual ML isolation slice. Populated-data output
parity, candidate migration rollout, a real worker identity/grant, sustained
worker recovery, physical Raspberry Pi acceptance, and overall MAN-CAP-040/047
acceptance remain open.
