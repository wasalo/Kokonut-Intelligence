from __future__ import annotations

import argparse
import json
import os
import re
import sys
from http.client import HTTPException, HTTPSConnection
from urllib.parse import urlparse


class SourceRunError(RuntimeError):
    pass


def _api_get(api_url: str, token: str, path: str) -> dict:
    parsed_url = urlparse(api_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise SourceRunError("GitHub API URL must be a valid HTTPS origin")
    request_path = f"{parsed_url.path.rstrip('/')}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=30) as connection:
            connection.request("GET", request_path, headers=headers)
            response = connection.getresponse()
            if response.status < 200 or response.status >= 300:
                raise SourceRunError(
                    f"GitHub API request failed with HTTP {response.status}: {path.split('?')[0]}"
                )
            payload = json.loads(response.read())
    except (HTTPException, OSError, TimeoutError, json.JSONDecodeError) as error:
        raise SourceRunError(f"GitHub API request failed: {path.split('?')[0]}") from error
    if not isinstance(payload, dict):
        raise SourceRunError(f"GitHub API returned an invalid response: {path.split('?')[0]}")
    return payload


def _paginate(api_url: str, token: str, path: str, key: str) -> list[dict]:
    items = []
    for page in range(1, 101):
        separator = "&" if "?" in path else "?"
        payload = _api_get(api_url, token, f"{path}{separator}per_page=100&page={page}")
        page_items = payload.get(key)
        if not isinstance(page_items, list):
            raise SourceRunError(f"GitHub API response omitted {key}: {path.split('?')[0]}")
        if any(not isinstance(item, dict) for item in page_items):
            raise SourceRunError(f"GitHub API returned an invalid {key} entry: {path.split('?')[0]}")
        items.extend(page_items)
        if len(page_items) < 100:
            return items
    raise SourceRunError(f"GitHub API pagination exceeded 100 pages: {path.split('?')[0]}")


def _validate_run_identity(run: dict, repository: str, sha: str, workflow_path: str) -> None:
    repository_info = run.get("repository")
    head_repository_info = run.get("head_repository")
    run_repository = repository_info.get("full_name", "") if isinstance(repository_info, dict) else ""
    head_repository = head_repository_info.get("full_name", "") if isinstance(head_repository_info, dict) else ""
    if run_repository.casefold() != repository.casefold() or head_repository.casefold() != repository.casefold():
        raise SourceRunError("source workflow run does not belong to this repository")
    path = run.get("path", "")
    if not isinstance(path, str) or path.split("@", 1)[0] != workflow_path:
        raise SourceRunError(f"source run is not from {workflow_path}")
    if run.get("event") != "push" or run.get("head_branch") != "main":
        raise SourceRunError("source workflow run must be a push to main")
    if run.get("head_sha") != sha:
        raise SourceRunError("source workflow run SHA differs from the expected SHA")


def _require_success(run: dict, label: str) -> None:
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise SourceRunError(f"{label} workflow run did not complete successfully")


def _check_job(
    api_url: str,
    token: str,
    repository: str,
    run_id: int,
    sha: str,
    job: dict,
    expected_name: str,
) -> None:
    if job.get("name") != expected_name or job.get("status") != "completed" or job.get("conclusion") != "success":
        raise SourceRunError(f"required job did not pass: {expected_name}")
    check_url = urlparse(job.get("check_run_url", ""))
    api_host = urlparse(api_url).netloc
    check_match = re.fullmatch(
        rf"/repos/{re.escape(repository)}/check-runs/(\d+)",
        check_url.path,
        re.IGNORECASE,
    )
    if check_url.scheme != "https" or check_url.netloc != api_host or check_match is None:
        raise SourceRunError(f"required job has an invalid check-run reference: {expected_name}")
    check = _api_get(api_url, token, f"/repos/{repository}/check-runs/{check_match.group(1)}")
    details_path = urlparse(check.get("details_url", "")).path
    if (
        check.get("name") != expected_name
        or check.get("head_sha") != sha
        or check.get("status") != "completed"
        or check.get("conclusion") != "success"
        or (check.get("app") or {}).get("slug") != "github-actions"
        or re.search(rf"/actions/runs/{run_id}(?:/|$)", details_path) is None
    ):
        raise SourceRunError(f"required check run did not pass for this source run: {expected_name}")


def _workflow_job(
    api_url: str,
    token: str,
    repository: str,
    run_id: int,
    sha: str,
    job_name: str,
) -> None:
    jobs = _paginate(api_url, token, f"/repos/{repository}/actions/runs/{run_id}/jobs", "jobs")
    matches = [job for job in jobs if job.get("name") == job_name]
    if len(matches) != 1:
        raise SourceRunError(f"source workflow must contain exactly one {job_name} job")
    _check_job(api_url, token, repository, run_id, sha, matches[0], job_name)


def validate_source_run(
    *, api_url: str, token: str, repository: str, run_id: int, expected_sha: str
) -> dict[str, str | int]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise SourceRunError("repository must be an owner/name pair")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise SourceRunError("expected SHA must be a 40-character lowercase commit hash")
    parsed_api_url = urlparse(api_url)
    if parsed_api_url.scheme != "https" or not parsed_api_url.netloc:
        raise SourceRunError("GitHub API URL must use HTTPS")
    if not token:
        raise SourceRunError("GitHub token is required for source-run validation")
    if run_id <= 0:
        raise SourceRunError("source run ID must be a positive integer")

    ci_run = _api_get(api_url, token, f"/repos/{repository}/actions/runs/{run_id}")
    _validate_run_identity(ci_run, repository, expected_sha, ".github/workflows/ci.yml")
    _require_success(ci_run, "CI")
    _workflow_job(api_url, token, repository, run_id, expected_sha, "ci")
    _workflow_job(api_url, token, repository, run_id, expected_sha, "kernel-image")

    security_runs = _paginate(
        api_url,
        token,
        f"/repos/{repository}/actions/workflows/security.yml/runs?head_sha={expected_sha}&branch=main&event=push",
        "workflow_runs",
    )
    matching_security_runs = []
    for run in security_runs:
        try:
            _validate_run_identity(run, repository, expected_sha, ".github/workflows/security.yml")
        except SourceRunError:
            continue
        matching_security_runs.append(run)
    if not matching_security_runs:
        raise SourceRunError("no Security workflow run exists for the expected main commit")
    security_run = max(
        matching_security_runs,
        key=lambda run: (
            int(run.get("run_number", 0)),
            int(run.get("run_attempt", 0)),
            str(run.get("updated_at", "")),
        ),
    )
    _require_success(security_run, "Security")
    security_run_id = int(security_run.get("id", 0))
    if security_run_id <= 0:
        raise SourceRunError("Security workflow run has an invalid run ID")
    _workflow_job(api_url, token, repository, security_run_id, expected_sha, "gitleaks")

    artifacts = _paginate(
        api_url,
        token,
        f"/repos/{repository}/actions/runs/{run_id}/artifacts",
        "artifacts",
    )
    artifact_name = f"kokonut-kernel-postgis-{expected_sha}-{run_id}"
    matching_artifacts = [artifact for artifact in artifacts if artifact.get("name") == artifact_name]
    if len(matching_artifacts) != 1:
        raise SourceRunError("source CI run does not contain exactly one expected PostGIS OCI artifact")
    artifact = matching_artifacts[0]
    digest = artifact.get("digest", "")
    artifact_id = artifact.get("id")
    if (
        artifact.get("expired") is not False
        or not isinstance(artifact_id, int)
        or artifact_id <= 0
        or not isinstance(artifact.get("size_in_bytes"), int)
        or artifact["size_in_bytes"] <= 0
        or not isinstance(digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
    ):
        raise SourceRunError("expected PostGIS OCI artifact is expired or has invalid metadata")

    return {
        "artifact_id": artifact_id,
        "artifact_digest": digest,
        "artifact_name": artifact_name,
        "source_sha": expected_sha,
        "source_run_id": run_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args()
    api_url = os.environ.get("GITHUB_API_URL", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    try:
        result = validate_source_run(
            api_url=api_url,
            token=token,
            repository=repository,
            run_id=args.run_id,
            expected_sha=args.expected_sha,
        )
        with open(args.github_output, "a", encoding="utf-8") as output:
            for key, value in result.items():
                output.write(f"{key}={value}\n")
    except (OSError, SourceRunError) as error:
        print(f"PostGIS source-run validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
