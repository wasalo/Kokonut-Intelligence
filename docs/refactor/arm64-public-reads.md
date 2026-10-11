# ARM64 public-read image refresh — 10 October 2026

The default Kernel target rebuilt successfully as
`kokonut-kernel-candidate-arm64:local`, inspected image identity
`sha256:fd9ed5a206e98c6c0fff4713618e624872ad6b0dc3392a7c306bac5aad9a0b45`.
Docker reports linux/arm64 and configured user appuser. Reported image size is
112,228,405 bytes; this is not an installed-filesystem or memory budget measurement.

This artifact includes the latest bounded native location/metric reads,
published CRISP read, governed location roll-up, explicit public response models,
schema/extension readiness gate, read-only readiness CLI, and migrations 371–373.
It was built from the uncommitted checkout on chore/kernel-plan-ignore based on
commit ad806f504bfef15cba41446d777cb22f6bd8fe6a; the commit alone does not identify
the implementation source.

Dependency installation and embedded inventory layers were reused from the
previous ARM64 readiness build. That earlier extracted inventory contains 68
packages matching its paired AMD64 build. No fresh dependency resolution or
inventory extraction was performed in this slice. The same dependency manifests
remain selected; version hashes/locking and release provenance are still pending.

## Runtime scope and rollback

No container was started from this ARM64 artifact, no schema was applied to an
ARM64 database, and no tests or live route requests ran. The running portability
stack is AMD64 and was unchanged. Earlier ARM64 readiness artifact identity
`sha256:a335b9d370575363d5fc80e7970511e9150d5f4a23353d8827af749ffbd5ef80`
remains the recorded prior build; the mutable local tag now points to this refresh.
Retain required artifacts before pruning Docker images.

Build completion does not certify native imports, generated OpenAPI, populated
public responses, authorization, worker recovery, spatial operations, backups,
or a 4 GB Raspberry Pi budget. Optional transport/analytics targets were not
rebuilt. The main candidate planner still rejects ARM64 because its selected
database manifest remains AMD64-only. The separate portability evaluation path
requires rebuilding its own app/database tags for the selected architecture;
this artifact does not change that path's currently running AMD64 services.

No data rollback is needed for this build-only refresh. Native ARM64 runtime,
clean-bootstrap/restore acceptance, and Pi hardware measurement remain required
before declaring the edge profile ready.
