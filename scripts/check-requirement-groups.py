#!/usr/bin/env python3
"""Keep additive dependency manifests aligned with the legacy constraints."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requirements(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def main() -> int:
    expected = Counter(requirements(ROOT / "requirements.txt"))
    actual = Counter()
    manifests = sorted((ROOT / "requirements").glob("*.txt"))
    for path in manifests:
        actual.update(requirements(path))
    missing, extra = expected - actual, actual - expected
    if missing or extra:
        for value, count in sorted(missing.items()):
            print(f"Missing constraint ({count}): {value}")
        for value, count in sorted(extra.items()):
            print(f"Unexpected/duplicated constraint ({count}): {value}")
        return 1
    print(f"Dependency groups aligned ({len(manifests)} groups, {sum(expected.values())} requirements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
