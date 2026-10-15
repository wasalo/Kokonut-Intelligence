# Optional Directus Kernel profile

Directus is an optional administration and compatibility adapter. It is not a
dependency of the minimal, edge, standard, or analytics Kernel profiles. The
profile runs the pinned Directus 12.1.1 image under a dedicated DML-only
`kokonut_directus_runtime` database login and binds to loopback port 18055 by
default. Redis is disabled for this service configuration.

## Prepare the isolated candidate

Use only the standalone Kernel candidate database. Do not combine this profile
with the legacy Compose project or point it at a shared/legacy PostgreSQL
instance. Keep the PostgreSQL owner password and Directus runtime password
distinct and in encrypted secrets.

Build the ignored Directus extension artifact and prepare the ordered schema:

```sh
make hooks-build
source scripts/load-secrets.sh
python3 scripts/kernel-profile.py minimal --directus
python3 scripts/check-directus-role-disposable.py
python3 scripts/check-directus-profile-disposable.py
```

The profile planner prints a Compose command; it does not execute it. The
disposable role check creates and removes an internal-only PostgreSQL project
with synthetic credentials. The profile check exercises the actual overlay,
including owner bootstrap, runtime health, synthetic admin login, and database
identity, then removes its volume. For repeatable candidate operations, set a
project name and use the two explicit manifests:

```sh
source scripts/load-secrets.sh
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-directus.yml \
  --profile directus-admin run --rm directus-role-bootstrap
```

The role bootstrap is an instance-level security operation: it revokes
`PUBLIC CONNECT` across the dedicated candidate PostgreSQL cluster, removes
stale Directus grants, and grants the Directus login only the application
database. It preserves explicit grants assigned to separately provisioned
service roles. Do not run it on a shared or legacy PostgreSQL server.

Apply reviewed schemas before initializing Directus metadata. The separate
owner-backed bootstrap is a one-shot and must complete before the service
starts:

```sh
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-directus.yml \
  --profile directus-admin run --rm directus-bootstrap

docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-directus.yml \
  up -d directus
```

The API is available on `http://127.0.0.1:18055` unless the loopback port is
overridden. The upload volume is named `kernel-directus-uploads`; include it in
the approved backup and restore set. The legacy Directus container and its
volume are not altered by this profile.

## Acceptance boundary

The Compose overlay and role bootstrap establish a deployment path and a
non-owner service identity. They do not establish role, field, relation,
tenant, lifecycle, or schedule parity. The OIDC issuer must match the Gateway,
Directus users must map to enabled Kokonut operator identities, and grants must
be provisioned only after collection/action/field scopes are reviewed. The
current unlicensed Directus image denies `farm_activity` rules that use custom
permissions; do not widen access to make the service probe pass. Use the native
Gateway for operational writes until the scoped Directus parity inventory is
accepted.
