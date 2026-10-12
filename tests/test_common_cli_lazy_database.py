from __future__ import annotations

import os
import subprocess
import sys


def test_non_database_cli_helpers_do_not_load_database_credentials():
    code = (
        "import sys; from services.common.cli import print_json; "
        "assert 'services.common.database' not in sys.modules; "
        "print_json({'database_write': False})"
    )
    env = {**os.environ, "KOKONUT_ENV": "development"}
    env.pop("KOKONUT_ALLOW_PLAINTEXT_ENV", None)

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        env=env,
        text=True,
        timeout=20,
    )

    assert '"database_write": false' in result.stdout
    assert "SOPS" not in result.stderr


def test_unified_cli_registers_optional_command_groups_without_loading_database():
    code = (
        "import sys; import services.cli; "
        "assert 'services.common.database' not in sys.modules; "
        "assert 'services.governance.baal' not in sys.modules"
    )
    env = {**os.environ, "KOKONUT_ENV": "development"}
    env.pop("KOKONUT_ALLOW_PLAINTEXT_ENV", None)

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        env=env,
        text=True,
        timeout=20,
    )

    assert "SOPS" not in result.stderr
