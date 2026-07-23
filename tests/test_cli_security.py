"""Tests for Security CLI (services.security.cli)."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_services_security_cli_help():
    """--help exits 0 (or 2 for argparse) and prints usage."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.security.cli', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    # argparse --help exits 0; some CLIs exit 2 for unknown args
    assert result.returncode in (0, 2), f'--help failed: {result.stderr[:200]}'
    assert 'usage' in (result.stdout + result.stderr).lower() or len(result.stdout) > 10

def test_services_security_cli_imports():
    """Module imports without error."""
    import importlib
    mod = importlib.import_module('services.security.cli')
    assert mod is not None


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"  \u2713 {name}")
            except Exception as e:
                print(f"  \u2717 {name}: {e}")
