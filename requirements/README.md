# Candidate Kernel dependency groups

These additive manifests copy every direct requirement and version constraint
from the legacy `requirements.txt`. Legacy images continue using that complete
manifest; the Kernel image uses the selected hash-locked closure below.

| Manifest | Intended dependency area |
| --- | --- |
| kernel.txt | PostgreSQL, CLI, HTTP, gateway, XML safety |
| web3.txt | Web3 client and ABI support |
| exports.txt | Object storage and spreadsheet support |
| storage.txt | Authenticated encryption for local private media |
| clickhouse.txt | Optional ClickHouse client only |
| analytics.txt | Full tabular analytics, forecasting, and market data |
| ml-anomaly.txt | Small optional dependency subset for sensor-anomaly modeling |
| geospatial.txt | Earth Engine and GIS file access |
| oidc.txt | Optional operator OIDC integration |
| orchestration.txt | Prefect |
| mqtt.txt | Paho sensor/actuator transport |
| grpc.txt | gRPC, generated bindings tooling, protobuf |
| dev.txt | Python test runner and Starlette ASGI test client |
| kernel-runtime.in / kernel-runtime.lock | Standard Kernel runtime input and hash-locked transitive closure |
| kernel-clickhouse.in / kernel-clickhouse.lock | Standard runtime plus hash-locked optional ClickHouse closure |
| ml-anomaly-runtime.in | Narrow optional ML worker runtime input: model packages plus psycopg2, with compatibility ranges (not yet hash-locked) |

Install selected groups with repeated `-r` arguments. For example:

    python3 -m pip install -r requirements/kernel.txt -r requirements/web3.txt

These are dependency candidates, not certified deployment profiles.
`kernel.txt` covers inspected gateway startup paths and PostgreSQL infrastructure;
it does not certify all lazily loaded endpoints, jobs, exports, or domain CLIs.
Media object storage currently requires the exports group. Web3 capability users
require the Web3 group even when no local blockchain node is deployed.
The sensor-anomaly worker installs `ml-anomaly-runtime.in`: the five model
packages from `ml-anomaly.txt` (pandas, NumPy, Prophet, scikit-learn, and
SciPy) plus the PostgreSQL driver, rather than the full Kernel dependency
closure or unrelated market-data/geostatistics packages. These numerical
libraries can still be substantial on an edge device; ARM64 software builds do
not establish runtime resource suitability.

The standard and optional ClickHouse image lockfiles pin resolved versions and
artifact hashes. The optional ML worker currently uses compatibility ranges,
not a hash-locked transitive closure; its current AMD64 and ARM64 images measure
about 955 MB and 987 MB respectively. Package resolution, runtime imports,
compatibility suites, and ARM64 software builds pass for this slice, but image
weight remains material for edge devices. Do not remove packages from legacy
images until capability checks pass. Keep constraints synchronized with
`requirements.txt` during transition.

Regenerate both Kernel locks with `pip-tools==7.6.2` using the commands in
[`docs/refactor/kernel-release-inputs.md`](../docs/refactor/kernel-release-inputs.md).
The current locks do not pin apt dependencies or the Python base image's bundled
pip independently from the digest.

`python3 scripts/check-requirement-groups.py` checks that the union of the
dependency groups exactly matches the legacy constraints, including duplicate
counts. It also verifies that `ml-anomaly.txt` stays an exact subset of
`analytics.txt` without double-counting it in that union. It runs in the
fast-fail CI gate and uses no external packages.

Rollback: point the Kernel Dockerfile back to the compatible group manifests;
legacy images, services, and data remain independent of these locks.
