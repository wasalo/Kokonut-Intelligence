# Candidate Kernel dependency groups

These additive manifests copy every direct requirement and version constraint
from the legacy `requirements.txt`. Existing images and CI continue using that
complete manifest. No default installation changes in this step.

| Manifest | Intended dependency area |
| --- | --- |
| kernel.txt | PostgreSQL, CLI, HTTP, gateway, XML safety |
| web3.txt | Web3 client and ABI support |
| exports.txt | Object storage and spreadsheet support |
| storage.txt | Authenticated encryption for local private media |
| clickhouse.txt | Optional ClickHouse client only |
| analytics.txt | Tabular analytics, forecasting, ML, market data |
| geospatial.txt | Earth Engine and GIS file access |
| oidc.txt | Optional operator OIDC integration |
| orchestration.txt | Prefect |
| mqtt.txt | Paho sensor/actuator transport |
| grpc.txt | gRPC, generated bindings tooling, protobuf |
| dev.txt | Python test runner and Starlette ASGI test client |

Install selected groups with repeated `-r` arguments. For example:

    python3 -m pip install -r requirements/kernel.txt -r requirements/web3.txt

These are dependency candidates, not certified deployment profiles.
`kernel.txt` covers inspected gateway startup paths and PostgreSQL infrastructure;
it does not certify all lazily loaded endpoints, jobs, exports, or domain CLIs.
Media object storage currently requires the exports group. Web3 capability users
require the Web3 group even when no local blockchain node is deployed.
Analytics/geospatial include workloads unsuitable for a small edge device and
will need further splitting before ARM64 resource certification.

Transitive dependency weight remains unmeasured. These files preserve version
ranges rather than locking a complete environment. Package resolution, image
builds, runtime imports, compatibility suites, and ARM64 wheel availability are
pending. Do not remove packages from the existing images until capability checks
pass. Keep constraints synchronized with `requirements.txt` during transition.

`python3 scripts/check-requirement-groups.py` checks that the union of these twelve
groups exactly matches the legacy constraints, including duplicate counts.
It runs in the fast-fail CI gate and uses no external packages.

Rollback: remove these unused additive manifests. No image, service, or data
changes have occurred.
