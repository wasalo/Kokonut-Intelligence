"""Contracts for verifiable source metadata on Kernel image builds."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from runpy import run_path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATE = run_path(str(ROOT / "scripts" / "check-kernel-release-inputs.py"))
SOURCE_REPOSITORY = RELEASE_GATE["SOURCE_REPOSITORY"]
SOURCE_LABEL = RELEASE_GATE["SOURCE_LABEL"]
REVISION_LABEL = RELEASE_GATE["REVISION_LABEL"]
LOCK_ERROR = RELEASE_GATE["LockError"]
COOLIFY_RENDERER = run_path(str(ROOT / "scripts" / "render-kernel-coolify-compose.py"))


def _image_config(*, source: str, revision: str) -> dict:
    return {"config": {"Labels": {SOURCE_LABEL: source, REVISION_LABEL: revision}}}


def test_kernel_oci_source_labels_accept_the_expected_repository_and_revision() -> None:
    RELEASE_GATE["_validate_source_labels"](
        _image_config(source=SOURCE_REPOSITORY, revision="a" * 40),
        architecture="amd64",
        expected_source_commit="a" * 40,
    )


@pytest.mark.parametrize(
    ("source", "revision"),
    [
        ("https://example.invalid/wrong", "a" * 40),
        (SOURCE_REPOSITORY, "b" * 40),
        (SOURCE_REPOSITORY, ""),
    ],
)
def test_kernel_oci_source_labels_reject_wrong_or_missing_provenance(source: str, revision: str) -> None:
    with pytest.raises(LOCK_ERROR, match="source labels mismatch"):
        RELEASE_GATE["_validate_source_labels"](
            _image_config(source=source, revision=revision),
            architecture="arm64",
            expected_source_commit="a" * 40,
        )


def test_kernel_build_targets_declare_revision_only_at_the_final_image_stage() -> None:
    dockerfile = (ROOT / "Dockerfile.kernel").read_text(encoding="utf-8")
    stages: dict[str, list[str]] = {}
    current_stage = None
    for line in dockerfile.splitlines():
        match = re.match(r"^FROM\b.*\bAS\s+(\S+)\s*$", line, re.IGNORECASE)
        if match:
            current_stage = match.group(1)
            stages[current_stage] = []
        elif current_stage:
            stages[current_stage].append(line)

    for target in ("kernel", "kernel-core", "oidc", "grpc", "mqtt", "ml-anomaly"):
        stage = "\n".join(stages[target])
        assert "ARG SOURCE_COMMIT=unknown" in stage
        assert "org.opencontainers.image.source" in stage
        assert 'org.opencontainers.image.revision="${SOURCE_COMMIT}"' in stage


def test_coolify_standard_compose_passes_revision_to_both_runtime_images() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-coolify.yml").read_text(encoding="utf-8"))
    for service_name, service in compose["services"].items():
        build = service.get("build", {})
        if Path(str(build.get("dockerfile", "Dockerfile"))).name != "Dockerfile.kernel":
            continue
        build_args = build["args"]
        assert build_args["SOURCE_COMMIT"] == "${SOURCE_COMMIT:-unknown}"


def test_coolify_compose_uses_string_sequence_labels_for_compatible_merging() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-coolify.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    for service_name, service in services.items():
        labels = service.get("labels")
        if labels is not None:
            assert isinstance(labels, list), service_name
            assert all(isinstance(label, str) and label for label in labels), service_name

    app_labels = set(services["app"]["labels"])
    assert "traefik.enable=true" in app_labels
    assert "coolify.applicationUuid=${COOLIFY_RESOURCE_UUID:?Coolify resource UUID is required}" in app_labels


def test_coolify_compose_scopes_project_networks_and_volumes_to_resource_uuid() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-coolify.yml").read_text(encoding="utf-8"))
    resource_uuid = "${COOLIFY_RESOURCE_UUID:?Coolify resource UUID is required}"

    assert compose["name"] == resource_uuid
    for network_name, network in compose["networks"].items():
        if network.get("external") is True:
            continue
        assert network["name"] == f"{resource_uuid}_{network_name}"
    for volume_name, volume in compose["volumes"].items():
        if volume.get("external") is True:
            continue
        assert volume["name"] == f"{resource_uuid}_{volume_name}"

    invalid = deepcopy(compose)
    invalid["volumes"]["kernel-postgres-data"]["name"] = (
        "kokonut-kernel-coolify_kernel-postgres-data"
    )
    with pytest.raises(RuntimeError, match="must be scoped to COOLIFY_RESOURCE_UUID"):
        COOLIFY_RENDERER["_validate_coolify_resource_names"](invalid)


def test_coolify_host_paths_are_relative_and_traversal_free() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-coolify.yml").read_text(encoding="utf-8"))
    validate_paths = COOLIFY_RENDERER["_validate_coolify_host_resource_paths"]

    validate_paths(compose["services"])

    unsafe_paths = (
        {
            "gateway": {
                "volumes": [
                    {
                        "type": "bind",
                        "source": "/data/coolify/applications/${COOLIFY_RESOURCE_UUID}/private/media.env",
                    }
                ]
            }
        },
        {"gateway": {"volumes": [{"type": "bind", "source": "./private/../outside.env"}]}},
        {"gateway": {"env_file": [{"path": "./private/${SERVICE}.env"}]}},
    )
    for services in unsafe_paths:
        with pytest.raises(RuntimeError, match="relative, traversal-free, and not interpolated"):
            validate_paths(services)


def test_coolify_app_and_worker_mark_scoped_environment_injected() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-coolify.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    for service_name in ("app", "worker"):
        assert services[service_name]["environment"]["KOKONUT_ENV_SECRETS_INJECTED"] == "true"
    for service_name, service in services.items():
        if service_name not in {"app", "worker"}:
            assert "KOKONUT_ENV_SECRETS_INJECTED" not in service.get("environment", {})


@pytest.mark.parametrize(
    "filename",
    [
        "docker-compose.kernel-candidate.yml",
        "docker-compose.kernel-standard.yml",
        "docker-compose.kernel-analytics-role.yml",
        "docker-compose.kernel-directus.yml",
        "docker-compose.kernel-grpc.yml",
        "docker-compose.kernel-http-sensors.yml",
        "docker-compose.kernel-metabase.yml",
        "docker-compose.kernel-mqtt.yml",
        "docker-compose.kernel-portability.yml",
        "docker-compose.kernel-recovery-directus-role.yml",
        "docker-compose.kernel-runtime-role.yml",
        "docker-compose.kernel-sensor-anomaly-ml.yml",
    ],
)
def test_kernel_compose_builds_pass_source_commit(filename: str) -> None:
    compose = yaml.safe_load((ROOT / filename).read_text(encoding="utf-8"))
    for service_name, service in compose["services"].items():
        build = service.get("build", {})
        if Path(str(build.get("dockerfile", "Dockerfile"))).name != "Dockerfile.kernel":
            continue
        assert build["args"]["SOURCE_COMMIT"] == "${SOURCE_COMMIT:-unknown}", service_name


def test_ci_and_release_workflows_supply_the_checked_out_revision() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/publish-kernel-images.yml").read_text(encoding="utf-8")
    assert "SOURCE_COMMIT: ${{ github.sha }}" in ci
    assert '--build-arg "SOURCE_COMMIT=${GITHUB_SHA}"' in release
