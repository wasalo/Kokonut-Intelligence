# Application dependency inventories

Future `Dockerfile.kernel` builds retain `/app/python-packages.json` and
`/app/python-runtime.txt` inside the image. The JSON comes from pip's installed
distribution inventory and includes transitive packages and packaging tools.
The runtime file records the Python interpreter version and build description.
Neither file reads secrets, connects to services, or imports application modules.

The base target records packages after the optional ClickHouse installation.
The gRPC and MQTT targets replace the package inventory after adding their
transport dependencies. The final Kernel target inherits the base inventory.
This prevents optional-target evidence from silently describing only the base.

## Release use

Retain these files with the inspected image identity, target, platform, source
revision, dependency manifests, and database package inventory. Compare package
names and versions across AMD64 and ARM64 before selecting release artifacts.
Existing recorded images predate this addition and do not contain these files;
their build logs remain the available installation evidence.

An installed-package list is not a dependency lock: it lacks wheel hashes,
resolver inputs, artifact provenance, and a repository snapshot. Version ranges
can still resolve differently on a rebuild. Selecting a reviewed lock strategy
and rebuilding both architectures remain release prerequisites. Equal package
versions also do not establish runtime or native-wheel compatibility.

## Current status and rollback

The Dockerfile changes are prepared but no image was rebuilt or deployed in this
initial slice. The subsequent [paired readiness builds](builds/2026-10-10-readiness/README.md)
contain extracted inventories with 68 matching package names/versions on both
architectures. No tests ran. Runtime and native-artifact compatibility remain pending.
Rollback selects the prior image identity; this change creates no database state
and changes no existing containers or volumes.
