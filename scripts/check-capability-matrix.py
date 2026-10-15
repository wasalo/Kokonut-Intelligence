#!/usr/bin/env python3
"""Check that the refactor capability ledger is complete and structurally valid."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/refactor/capability-matrix.md"
EXPECTED_IDS = [f"CAP-{number:03d}" for number in range(1, 67)]
STATUS_PREFIX = re.compile(r"^([BDP])\s+—\s+")
PATH_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:tests|services|schemas|extensions|contracts|proto|sdk)/"
    r"[A-Za-z0-9_./-]+"
)


def check_matrix() -> list[str]:
    errors: list[str] = []
    rows: list[tuple[int, list[str]]] = []

    for line_number, line in enumerate(MATRIX.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| CAP-"):
            continue

        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) != 6:
            errors.append(
                f"{MATRIX.relative_to(ROOT)}:{line_number}: expected 6 cells, found {len(cells)}"
            )
            continue
        rows.append((line_number, cells))

    ids = [cells[0] for _, cells in rows]
    if ids != EXPECTED_IDS:
        missing = sorted(set(EXPECTED_IDS) - set(ids))
        extra = sorted(set(ids) - set(EXPECTED_IDS))
        duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
        errors.append(
            "capability IDs must appear once in order CAP-001..CAP-066; "
            f"missing={missing}, extra={extra}, duplicates={duplicates}"
        )

    statuses: Counter[str] = Counter()
    for line_number, cells in rows:
        capability_id, _name, owner, manual_check, test_candidates, progress = cells
        if capability_id not in manual_check:
            errors.append(f"{MATRIX.relative_to(ROOT)}:{line_number}: manual check must name {capability_id}")

        status = STATUS_PREFIX.match(progress)
        if not status:
            errors.append(
                f"{MATRIX.relative_to(ROOT)}:{line_number}: progress must begin with B, D, or P and an em dash"
            )
        else:
            statuses[status.group(1)] += 1

        for source_path in PATH_REFERENCE.findall(owner):
            if not (ROOT / source_path).exists():
                errors.append(f"{MATRIX.relative_to(ROOT)}:{line_number}: missing code owner path {source_path}")
        for test_path in PATH_REFERENCE.findall(test_candidates):
            if not (ROOT / test_path).exists():
                errors.append(f"{MATRIX.relative_to(ROOT)}:{line_number}: missing test candidate {test_path}")

    if not errors:
        print(
            f"Capability matrix valid: {len(rows)} rows; "
            f"{statuses['B']} baseline-retained, {statuses['D']} deployed, "
            f"{statuses['P']} prepared; MAN-CAP checks remain separately gated."
        )
    return errors


def main() -> int:
    errors = check_matrix()
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
