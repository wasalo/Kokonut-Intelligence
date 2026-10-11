# Optional native workers in the portability stack

**Subsequent startup:** the [AMD64 runtime record](portability-runtime.md) now
records the worker running after an empty-backlog review. Preparation-only
statements below describe the earlier implementation slice; durability and ARM64
runtime acceptance remain pending.

The standalone portability manifest now includes a `worker` service behind the
explicit `workers` Compose profile. It inherits the API's platform, image/build,
private network, production PostgreSQL settings, disabled vendor providers,
init handling, 40-second stop period, and restart=no evaluation policy.
YAML anchors keep those settings aligned without a second provider inventory.

Its command is `services.core.runtime --workers-only --require-schema`. The
supervisor checks bundled migration checksums and required extensions before
starting the native database scheduler and event worker. Their feature flags are
explicitly enabled in this role. The API command still starts only the API.
The worker exposes no host ports and disables the image's HTTP healthcheck.
Process state alone does not establish durable worker progress; inspect task/run
and event-delivery records through the existing operator commands.

## Preparation and selection

The portability command planner accepts `--with-workers` to add the profile to
its printed command. It still executes nothing and offers no startup action.
An explicitly named service can bypass Compose profile selection, so review the
service names as well as profile flags before executing a command.

```sh
python3 scripts/kernel-portability.py --target-platform linux/amd64 --with-workers
python3 scripts/kernel-portability.py --target-platform linux/arm64 --with-workers --action ps
```

Before starting workers, apply the schema inventory to the correct database,
review enabled scheduled-task definitions/dependencies and event backlog, and
choose the scheduler owner. Startup dispatches eligible persisted work; disabled
vendor providers do not disable every native job or prevent its external calls.
No task is created or activated by this manifest change. Scheduler graph
activation retains its separate audited operator flow.

For the existing isolated AMD64 deployment, after that review and loading
encrypted secrets, the explicit worker-only startup command is:

```sh
KOKONUT_DATABASE_PLATFORM=linux/amd64 docker compose --env-file /dev/null \
  -p kokonut-kernel-portability -f docker-compose.kernel-portability.yml \
  --profile workers up -d --no-build --no-deps worker
```

This requires the database to be running already and the matching app image to
be built. It does not apply migrations or reconcile jobs. Do not combine this
manifest with candidate/legacy overlays or point its worker at their databases.

## Current status and rollback

The worker profile passed quiet Compose parsing on AMD64 and ARM64. Lint and
static checks passed. No worker was started, no task/event was processed, and no
test suite ran. The existing portability database/API remain the running roles;
their state is documented in [the runtime record](portability-runtime.md).
Worker durability, retries, lease recovery, shutdown, and ARM64 runtime acceptance
remain pending. This does not certify the standard or scale deployment profiles.

If selected later, stop only `worker` in this explicit project with the same
platform. Preserve its database, leases, run history, and event-delivery state.
Allow the graceful stop period before diagnosing or replaying work; use existing
operator replay/disposal commands rather than deleting rows or resetting leases.
Reverting the profile declaration alone does not stop an already running worker.
