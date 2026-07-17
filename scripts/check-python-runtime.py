#!/usr/bin/env python3
"""Validate the Python runtime supported by Kokonut Intelligence."""

from __future__ import annotations

import ssl
import sys


MINIMUM_PYTHON = (3, 11)


def main() -> int:
    version = sys.version_info[:3]
    if version < MINIMUM_PYTHON:
        print(
            "ERROR: Kokonut Intelligence requires Python 3.11 or newer; "
            f"found {version[0]}.{version[1]}.{version[2]}.",
            file=sys.stderr,
        )
        return 1

    openssl_version = ssl.OPENSSL_VERSION
    if not openssl_version.startswith("OpenSSL "):
        print(
            "ERROR: Python must be built with OpenSSL; "
            f"found {openssl_version}.",
            file=sys.stderr,
        )
        return 1

    print(f"Python runtime supported: {sys.version.split()[0]} ({openssl_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
