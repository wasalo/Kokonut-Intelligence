from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publish-kernel-postgis-base.yml"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
BUILD_SCRIPT = ROOT / "scripts/build-kernel-multiarch.sh"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source_gate = _load_module("validate_kernel_postgis_source_run", ROOT / "scripts/validate-kernel-postgis-source-run.py")
published_gate = _load_module("verify_kernel_postgis_published", ROOT / "scripts/verify-kernel-postgis-published.py")
release_gate = _load_module("check_kernel_release_inputs", ROOT / "scripts/check-kernel-release-inputs.py")

SOURCE_SHA = "a" * 40
SOURCE_RUN_ID = 1001
SECURITY_RUN_ID = 2001
REPOSITORY = "kokonut-intelligence/kernel"
API_URL = "https://api.github.com"


def _workflow_run(run_id: int, workflow_path: str, *, conclusion: str = "success", run_number: int = 1) -> dict:
    return {
        "id": run_id,
        "run_number": run_number,
        "run_attempt": 1,
        "updated_at": "2026-11-05T00:00:00Z",
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
        "path": f"{workflow_path}@refs/heads/main",
        "event": "push",
        "head_branch": "main",
        "head_sha": SOURCE_SHA,
        "status": "completed",
        "conclusion": conclusion,
    }


def _job(name: str, check_id: int, run_id: int, *, conclusion: str = "success") -> dict:
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "check_run_url": f"{API_URL}/repos/{REPOSITORY}/check-runs/{check_id}",
    }


def _check(name: str, run_id: int, *, conclusion: str = "success") -> dict:
    return {
        "name": name,
        "head_sha": SOURCE_SHA,
        "status": "completed",
        "conclusion": conclusion,
        "app": {"slug": "github-actions"},
        "details_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/1",
    }


def _source_responses() -> dict[str, dict]:
    digest = "sha256:" + "b" * 64
    return {
        f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}": _workflow_run(
            SOURCE_RUN_ID, ".github/workflows/ci.yml"
        ),
        f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/jobs?per_page=100&page=1": {
            "jobs": [_job("ci", 101, SOURCE_RUN_ID), _job("kernel-image", 102, SOURCE_RUN_ID)]
        },
        f"/repos/{REPOSITORY}/check-runs/101": _check("ci", SOURCE_RUN_ID),
        f"/repos/{REPOSITORY}/check-runs/102": _check("kernel-image", SOURCE_RUN_ID),
        f"/repos/{REPOSITORY}/actions/workflows/security.yml/runs?head_sha={SOURCE_SHA}&branch=main&event=push&per_page=100&page=1": {
            "workflow_runs": [_workflow_run(SECURITY_RUN_ID, ".github/workflows/security.yml")]
        },
        f"/repos/{REPOSITORY}/actions/runs/{SECURITY_RUN_ID}/jobs?per_page=100&page=1": {
            "jobs": [_job("gitleaks", 201, SECURITY_RUN_ID)]
        },
        f"/repos/{REPOSITORY}/check-runs/201": _check("gitleaks", SECURITY_RUN_ID),
        f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/artifacts?per_page=100&page=1": {
            "artifacts": [
                {
                    "id": 301,
                    "name": f"kokonut-kernel-postgis-{SOURCE_SHA}-{SOURCE_RUN_ID}",
                    "expired": False,
                    "size_in_bytes": 1024,
                    "digest": digest,
                }
            ]
        },
    }


def _validate_fixture(monkeypatch: pytest.MonkeyPatch, responses: dict[str, dict] | None = None) -> dict:
    payloads = responses or _source_responses()

    def fake_api_get(api_url: str, token: str, path: str) -> dict:
        assert api_url == API_URL
        assert token == "test-token"
        if path not in payloads:
            raise AssertionError(f"unexpected API request: {path}")
        return payloads[path]

    monkeypatch.setattr(source_gate, "_api_get", fake_api_get)
    return source_gate.validate_source_run(
        api_url=API_URL,
        token="test-token",
        repository=REPOSITORY,
        run_id=SOURCE_RUN_ID,
        expected_sha=SOURCE_SHA,
    )


def test_source_run_validation_accepts_only_successful_same_sha_main_gates_and_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _validate_fixture(monkeypatch)

    assert result == {
        "artifact_id": 301,
        "artifact_digest": "sha256:" + "b" * 64,
        "artifact_name": f"kokonut-kernel-postgis-{SOURCE_SHA}-{SOURCE_RUN_ID}",
        "source_sha": SOURCE_SHA,
        "source_run_id": SOURCE_RUN_ID,
    }


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("wrong_repository", "does not belong to this repository"),
        ("wrong_branch", "push to main"),
        ("wrong_sha", "differs from the expected SHA"),
        ("ci_failed", "CI workflow run did not complete successfully"),
        ("aggregate_failed", "required job did not pass: ci"),
        ("security_failed", "Security workflow run did not complete successfully"),
        ("gitleaks_failed", "required job did not pass: gitleaks"),
        ("artifact_missing", "does not contain exactly one expected PostGIS OCI artifact"),
        ("artifact_expired", "expired or has invalid metadata"),
        ("artifact_bad_digest", "expired or has invalid metadata"),
    ],
)
def test_source_run_validation_rejects_failed_or_mismatched_inputs(
    monkeypatch: pytest.MonkeyPatch, case: str, message: str
) -> None:
    responses = _source_responses()
    ci_key = f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}"
    ci_jobs_key = f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/jobs?per_page=100&page=1"
    security_key = (
        f"/repos/{REPOSITORY}/actions/workflows/security.yml/runs?head_sha={SOURCE_SHA}"
        "&branch=main&event=push&per_page=100&page=1"
    )
    artifact_key = f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/artifacts?per_page=100&page=1"
    if case == "wrong_repository":
        responses[ci_key]["repository"]["full_name"] = "other/repository"
    elif case == "wrong_branch":
        responses[ci_key]["head_branch"] = "develop"
    elif case == "wrong_sha":
        responses[ci_key]["head_sha"] = "c" * 40
    elif case == "ci_failed":
        responses[ci_key]["conclusion"] = "failure"
    elif case == "aggregate_failed":
        responses[ci_jobs_key]["jobs"][0]["conclusion"] = "failure"
    elif case == "security_failed":
        responses[security_key]["workflow_runs"][0]["conclusion"] = "failure"
    elif case == "gitleaks_failed":
        responses[f"/repos/{REPOSITORY}/actions/runs/{SECURITY_RUN_ID}/jobs?per_page=100&page=1"]["jobs"][0][
            "conclusion"
        ] = "failure"
    elif case == "artifact_missing":
        responses[artifact_key]["artifacts"] = []
    elif case == "artifact_expired":
        responses[artifact_key]["artifacts"][0]["expired"] = True
    elif case == "artifact_bad_digest":
        responses[artifact_key]["artifacts"][0]["digest"] = "sha256:mutable"

    with pytest.raises(source_gate.SourceRunError, match=message):
        _validate_fixture(monkeypatch, responses)


def test_latest_failed_security_rerun_overrides_an_older_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = _source_responses()
    security_key = (
        f"/repos/{REPOSITORY}/actions/workflows/security.yml/runs?head_sha={SOURCE_SHA}"
        "&branch=main&event=push&per_page=100&page=1"
    )
    latest = _workflow_run(SECURITY_RUN_ID + 1, ".github/workflows/security.yml", conclusion="failure", run_number=2)
    responses[security_key]["workflow_runs"].append(latest)

    with pytest.raises(source_gate.SourceRunError, match="Security workflow run did not complete successfully"):
        _validate_fixture(monkeypatch, responses)


def test_ci_retains_only_verified_main_postgis_artifact() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    kernel_job = workflow.split("\n  kernel-image:\n", 1)[1].split("\n  ci:\n", 1)[0]
    assert 'GITHUB_EVENT_NAME" == push && "$GITHUB_REF" == refs/heads/main' in kernel_job
    assert "--postgis-oci-output" in kernel_job
    assert "Upload checked PostGIS OCI artifact" in kernel_job
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in kernel_job
    assert "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9" in kernel_job
    assert "retention-days: 7" in kernel_job
    assert "if-no-files-found: error" in kernel_job
    assert kernel_job.index("Build and verify Kernel images") < kernel_job.index("Upload checked PostGIS OCI artifact")
    assert "needs: [preflight, source-checks, full-ci, kernel-image]" in workflow


def test_publisher_is_manual_main_only_protected_and_least_privileged() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    publisher_job = workflow.split("\n  publish:\n", 1)[1]

    assert "workflow_dispatch:" in workflow
    assert "options: [no, publish]" in workflow
    assert "source_run_id:" in workflow and "expected_sha:" in workflow
    assert "package_access:" in workflow
    assert "github.ref == 'refs/heads/main'" in publisher_job
    assert "environment:\n      name: kernel-release" in publisher_job
    assert "actions: read" in publisher_job
    assert "checks: read" in publisher_job
    assert "packages: write" in publisher_job
    assert workflow.count("packages: write") == 1
    assert "uses: oras-project/setup-oras@5e2f2482b30b0cb3e14e67f89a80c88c659a7c63" in workflow
    assert "version: 1.3.1" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "Confirm the GHCR package is private and repository-only read access is configured" in workflow


def test_publisher_checks_exact_artifact_and_inventory_before_copying() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validation = workflow.index("Validate successful main CI and Security source runs")
    download = workflow.index("Download and verify the exact source artifact")
    source_checkout = workflow.index("Check out the exact source-run commit")
    inventory_check = workflow.index("Recheck both PostGIS package inventories before publication")
    login = workflow.index("Authenticate to GitHub Container Registry")
    copy = workflow.index("oras cp --from-oci-layout")
    verify = workflow.index("Verify remote digest and multi-platform index")

    assert validation < download < source_checkout < inventory_check < login < copy < verify
    assert "ARTIFACT_DIGEST" in workflow
    assert "Downloaded GitHub artifact ZIP digest does not match its API metadata" in workflow
    assert "actions/artifacts/$ARTIFACT_ID/zip" in workflow
    assert "--postgis-oci \"$RUNNER_TEMP/kernel-postgis.oci.tar\"" in workflow
    assert "verified-${SOURCE_SHA}-${SOURCE_RUN_ID}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" in workflow
    assert "latest" not in workflow
    assert "docker buildx imagetools inspect --raw \"$repository@$digest\"" in workflow
    assert "verify-kernel-postgis-published.py" in workflow


def test_build_script_retains_postgis_oci_only_after_inventory_check() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    check = script.index('--postgis-oci "$BUILD_DIR/kernel-postgis.oci.tar"')
    retain = script.index('cp "$BUILD_DIR/kernel-postgis.oci.tar" "$POSTGIS_OUTPUT_TMP"')

    assert "--postgis-oci-output" in script
    assert "POSTGIS_OCI_OUTPUT=\"\"" in script
    assert "POSTGIS_OUTPUT_TMP" in script
    assert "rm -rf \"$BUILD_DIR\"" in script
    assert check < retain
    assert "--tag kokonut-kernel-postgis:verified" in script


def _published_index(platforms: list[str]) -> tuple[dict, bytes]:
    manifests = [
        {
            "digest": "sha256:" + ("c" if platform.endswith("amd64") else "d") * 64,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "size": 100,
            "platform": {"os": "linux", "architecture": platform.rsplit("/", 1)[1]},
        }
        for platform in platforms
    ]
    payload = json.dumps(
        {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": manifests},
        separators=(",", ":"),
    ).encode()
    descriptor = {
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
        "size": len(payload),
    }
    return descriptor, payload


def test_published_verifier_emits_only_immutable_multiarch_reference(tmp_path: Path) -> None:
    descriptor, payload = _published_index(["linux/amd64", "linux/arm64"])
    descriptor_path = tmp_path / "descriptor.json"
    manifest_path = tmp_path / "manifest.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    manifest_path.write_bytes(payload)

    result = published_gate.verify_published_image(
        descriptor_path,
        manifest_path,
        "ghcr.io/kokonut-intelligence/kernel-postgis-base",
    )

    assert result == (
        "ghcr.io/kokonut-intelligence/kernel-postgis-base@" + descriptor["digest"]
    )


@pytest.mark.parametrize(
    ("repository", "digest"),
    [
        ("ghcr.io/example/postgis:latest", "sha256:" + "a" * 64),
        ("ghcr.io/example/postgis", "latest"),
        ("ghcr.io/Example/postgis", "sha256:" + "a" * 64),
    ],
)
def test_published_verifier_rejects_mutable_or_noncanonical_references(repository: str, digest: str) -> None:
    with pytest.raises(published_gate.PublishedImageError):
        published_gate.immutable_reference(repository, digest)


def test_published_verifier_rejects_missing_duplicate_and_changed_architectures(tmp_path: Path) -> None:
    descriptor, payload = _published_index(["linux/amd64"])
    descriptor_path = tmp_path / "descriptor.json"
    manifest_path = tmp_path / "manifest.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    manifest_path.write_bytes(payload)
    with pytest.raises(published_gate.PublishedImageError, match="missing platforms: linux/arm64"):
        published_gate.verify_published_image(descriptor_path, manifest_path, "ghcr.io/example/postgis")

    descriptor, payload = _published_index(["linux/amd64", "linux/amd64", "linux/arm64"])
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    manifest_path.write_bytes(payload)
    with pytest.raises(published_gate.PublishedImageError, match="duplicate platform manifests"):
        published_gate.verify_published_image(descriptor_path, manifest_path, "ghcr.io/example/postgis")

    manifest_path.write_bytes(payload + b" ")
    with pytest.raises(published_gate.PublishedImageError, match="do not match the registry digest"):
        published_gate.verify_published_image(descriptor_path, manifest_path, "ghcr.io/example/postgis")


def _layer_bytes(package_text: str) -> bytes:
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode="w") as archive:
        content = package_text.encode()
        info = tarfile.TarInfo("usr/local/share/kokonut/database-packages.txt")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return layer.getvalue()


def _postgis_oci_archive(path: Path, *, scripts_arm64: str | None = None, architectures: tuple[str, ...] = ("amd64", "arm64")) -> None:
    blobs: dict[str, bytes] = {}
    descriptors = []
    package_version = "3.6.4+dfsg-2.pgdg12+1"
    scripts_version = scripts_arm64 or package_version
    for architecture in architectures:
        installed_scripts_version = scripts_version if architecture == "arm64" else package_version
        packages = [
            f"postgresql-16-postgis-3 {package_version}",
            f"postgresql-16-postgis-3-scripts {installed_scripts_version}",
        ]
        if architecture == "amd64":
            packages.append("libquadmath0 12.2.0-14+deb12u1")
        layer = _layer_bytes("\n".join(packages) + "\n")
        layer_digest = "sha256:" + hashlib.sha256(layer).hexdigest()
        blobs[layer_digest] = layer
        manifest_bytes = json.dumps(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:" + "e" * 64},
                "layers": [{"digest": layer_digest, "mediaType": "application/vnd.oci.image.layer.v1.tar"}],
            },
            separators=(",", ":"),
        ).encode()
        manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
        blobs[manifest_digest] = manifest_bytes
        descriptors.append(
            {
                "digest": manifest_digest,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "size": len(manifest_bytes),
                "platform": {"os": "linux", "architecture": architecture},
            }
        )
    index_bytes = json.dumps({"schemaVersion": 2, "manifests": descriptors}, separators=(",", ":")).encode()
    with tarfile.open(path, mode="w") as archive:
        for name, payload in {"index.json": index_bytes, **{f"blobs/sha256/{digest.split(':', 1)[1]}": data for digest, data in blobs.items()}}.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def test_postgis_inventory_checker_rejects_missing_architecture_and_package_mismatch(tmp_path: Path) -> None:
    lock = json.loads((ROOT / "config/kernel/release-input-lock.json").read_text(encoding="utf-8"))
    valid_archive = tmp_path / "valid-postgis.oci.tar"
    _postgis_oci_archive(valid_archive)
    release_gate._verify_postgis(valid_archive, lock)

    missing_arch = tmp_path / "missing-arm64.oci.tar"
    _postgis_oci_archive(missing_arch, architectures=("amd64",))
    with pytest.raises(release_gate.LockError, match="missing linux platform.*arm64"):
        release_gate._verify_postgis(missing_arch, lock)

    wrong_inventory = tmp_path / "wrong-inventory.oci.tar"
    _postgis_oci_archive(wrong_inventory, scripts_arm64="3.6.3+dfsg-1")
    with pytest.raises(release_gate.LockError, match="PostGIS package postgresql-16-postgis-3-scripts"):
        release_gate._verify_postgis(wrong_inventory, lock)
