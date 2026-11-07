"""Tests for deterministic full-suite test-file sharding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARDING_SCRIPT = ROOT / "scripts/pytest_test_sharding.py"


def _shard_files(repository_root: Path, test_root: Path, shard_count: int, shard_index: int) -> list[str]:
    result = subprocess.run(
        [
            sys.executable,
            str(SHARDING_SCRIPT),
            "--repository-root",
            str(repository_root),
            "--test-root",
            str(test_root),
            "--shard-count",
            str(shard_count),
            "--shard-index",
            str(shard_index),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_discovery_matches_pytest_patterns_and_ignores_generated_directories(tmp_path: Path) -> None:
    repository_root = tmp_path
    test_root = repository_root / "tests"
    for relative_path in (
        "test_alpha.py",
        "nested/beta_test.py",
        "nested/helper.py",
        ".hidden/test_hidden.py",
        "__pycache__/test_cached.py",
        "build/test_generated.py",
    ):
        path = test_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    assert _shard_files(repository_root, test_root, 3, 0) == ["tests/nested/beta_test.py"]
    assert _shard_files(repository_root, test_root, 3, 1) == ["tests/test_alpha.py"]
    assert _shard_files(repository_root, test_root, 3, 2) == []


def test_shards_cover_all_test_modules_once_in_contiguous_balanced_order(tmp_path: Path) -> None:
    repository_root = tmp_path
    test_root = repository_root / "tests"
    test_root.mkdir()
    for index in range(17):
        (test_root / f"test_{index:03}.py").write_text("", encoding="utf-8")

    shards = [_shard_files(repository_root, test_root, 6, index) for index in range(6)]
    flattened = [path for shard in shards for path in shard]

    assert flattened == sorted(flattened)
    assert flattened == [f"tests/test_{index:03}.py" for index in range(17)]
    assert len(flattened) == len(set(flattened))
    assert [len(shard) for shard in shards] == [3, 3, 3, 3, 3, 2]
