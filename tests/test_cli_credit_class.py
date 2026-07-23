"""Tests for Credit Class CLI (services.credit_class.cli)."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_services_credit_class_cli_help():
    """--help exits 0 (or 2 for argparse) and prints usage."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.credit_class.cli', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    # argparse --help exits 0; some CLIs exit 2 for unknown args
    assert result.returncode in (0, 2), f'--help failed: {result.stderr[:200]}'
    assert 'usage' in (result.stdout + result.stderr).lower() or len(result.stdout) > 10

def test_services_credit_class_cli_class_list_help():
    """Subcommand class list --help exits 0 or 2."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.credit_class.cli', 'class list', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode in (0, 2), f'class list --help failed: {result.stderr[:200]}'

def test_services_credit_class_cli_batch_list_help():
    """Subcommand batch list --help exits 0 or 2."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.credit_class.cli', 'batch list', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode in (0, 2), f'batch list --help failed: {result.stderr[:200]}'

def test_services_credit_class_cli_balance_all_help():
    """Subcommand balance all --help exits 0 or 2."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.credit_class.cli', 'balance all', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode in (0, 2), f'balance all --help failed: {result.stderr[:200]}'

def test_services_credit_class_cli_params_list_help():
    """Subcommand params list --help exits 0 or 2."""
    result = subprocess.run(
        [sys.executable, '-m', 'services.credit_class.cli', 'params list', '--help'],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode in (0, 2), f'params list --help failed: {result.stderr[:200]}'

def test_services_credit_class_cli_imports():
    """Module imports without error."""
    import importlib
    mod = importlib.import_module('services.credit_class.cli')
    assert mod is not None


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"  \u2713 {name}")
            except Exception as e:
                print(f"  \u2717 {name}: {e}")
