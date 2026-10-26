#!/usr/bin/env python3
"""Keep additive dependency manifests aligned with the legacy constraints."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_SUBSETS = {"ml-anomaly.txt": "analytics.txt"}


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
        if path.name not in OPTIONAL_SUBSETS:
            actual.update(requirements(path))
    for subset_name, parent_name in OPTIONAL_SUBSETS.items():
        subset = Counter(requirements(ROOT / "requirements" / subset_name))
        parent = Counter(requirements(ROOT / "requirements" / parent_name))
        missing_from_parent = subset - parent
        if missing_from_parent:
            for requirement, count in sorted(missing_from_parent.items()):
                print(
                    f"Optional subset {subset_name} is not contained in "
                    f"{parent_name}: {requirement} ({count})"
                )
            return 1
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
