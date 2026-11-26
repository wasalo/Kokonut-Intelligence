"""Classify changes that can safely skip database and image acceptance."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence

STATUS_ONLY_PATHS = frozenset({"docs/refactor/current-state-and-implementation.md"})
ZERO_SHA = "0" * 40


def should_run_expensive_gates(changed_paths: Sequence[str] | None) -> bool:
    """Fail closed unless every changed file is the canonical status document."""
    if not changed_paths:
        return True
    normalized = {Path(path).as_posix() for path in changed_paths}
    return not normalized or not normalized.issubset(STATUS_ONLY_PATHS)


def changed_paths_for_event(event_name: str, event: dict) -> list[str] | None:
    """Return changed paths for supported GitHub events, or None if unknown."""
    if event_name == "pull_request":
        pull_request = event.get("pull_request", {})
        base_sha = pull_request.get("base", {}).get("sha")
        head_sha = pull_request.get("head", {}).get("sha")
        revision = f"{base_sha}...{head_sha}"
    elif event_name == "push":
        base_sha = event.get("before")
        head_sha = event.get("after")
        revision = f"{base_sha}..{head_sha}"
    else:
        return None

    if not base_sha or not head_sha or base_sha == ZERO_SHA or base_sha == head_sha:
        return None

    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", revision],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not classify changed paths: {result.stderr.strip()}")
    paths = [line for line in result.stdout.splitlines() if line]
    return paths or None


def main() -> int:
    from os import environ

    event_path = environ.get("GITHUB_EVENT_PATH")
    event_name = environ.get("GITHUB_EVENT_NAME", "")
    event = json.loads(Path(event_path).read_text(encoding="utf-8")) if event_path else {}
    run_expensive = should_run_expensive_gates(changed_paths_for_event(event_name, event))
    print(f"expensive_gates={'true' if run_expensive else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
