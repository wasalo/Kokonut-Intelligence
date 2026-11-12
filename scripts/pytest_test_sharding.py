#!/usr/bin/env python3
"""Discover and partition pytest modules into deterministic sequential shards."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py")
_IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".nox",
    "build",
    "dist",
    "node_modules",
}


def discover_test_files(*, repository_root: Path, test_root: Path) -> list[str]:
    repository_root = repository_root.resolve()
    test_root = test_root.resolve()
    if not test_root.is_relative_to(repository_root):
        raise ValueError("test_root must be inside repository_root")

    discovered: set[str] = set()
    for pattern in _TEST_FILE_PATTERNS:
        for path in test_root.rglob(pattern):
            if not path.is_file():
                continue
            relative_to_tests = path.relative_to(test_root)
            if any(
                directory.startswith(".") or directory in _IGNORED_DIRECTORY_NAMES
                for directory in relative_to_tests.parts[:-1]
            ):
                continue
            discovered.add(path.relative_to(repository_root).as_posix())
    return sorted(discovered)


def partition_test_files(test_files: Sequence[str], shard_count: int) -> list[list[str]]:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")

    ordered_files = sorted(set(test_files))
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    if not ordered_files:
        return shards

    active_shards = min(shard_count, len(ordered_files))
    files_per_shard, remainder = divmod(len(ordered_files), active_shards)
    cursor = 0
    for shard_index in range(active_shards):
        shard_size = files_per_shard + (1 if shard_index < remainder else 0)
        shards[shard_index] = ordered_files[cursor : cursor + shard_size]
        cursor += shard_size
    return shards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--test-root", required=True, type=Path)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--count-only", action="store_true")
    arguments = parser.parse_args()

    try:
        test_files = discover_test_files(
            repository_root=arguments.repository_root,
            test_root=arguments.test_root,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if arguments.count_only:
        print(len(test_files))
        return 0
    if arguments.shard_count is None or arguments.shard_index is None:
        parser.error("--shard-count and --shard-index are required unless --count-only is used")

    try:
        shards = partition_test_files(test_files, arguments.shard_count)
    except ValueError as exc:
        parser.error(str(exc))
    if not 0 <= arguments.shard_index < len(shards):
        parser.error("shard index is outside the requested shard count")

    for path in shards[arguments.shard_index]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
