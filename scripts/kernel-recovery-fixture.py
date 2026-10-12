#!/usr/bin/env python3
"""Load disabled synthetic durable work only into the dedicated recovery fixture."""

import argparse
import hashlib
import json

from kernel_recovery_guard import CONTAINER, query, require_fixture_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Insert the disabled synthetic rows")
    args = parser.parse_args()
    root, schema_files = require_fixture_database()
    sql = (root / "scripts/fixtures/kernel-recovery-work.sql").read_text()
    if args.apply:
        query(sql)
    print(json.dumps({"applied": args.apply, "container": CONTAINER,
                      "schema_files": schema_files, "seed_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                      "scope": "Disabled synthetic work only; media/device fixture and recovery acceptance remain open."}))


if __name__ == "__main__":
    main()
