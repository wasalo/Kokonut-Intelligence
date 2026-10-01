from __future__ import annotations

import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PERMISSION_HELPER = REPO_ROOT / "deploy/scripts/set-staging-env-permissions.sh"


class StagingEnvPermissionTests(unittest.TestCase):
    def test_encrypted_env_is_readable_by_age_key_group_without_changing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            age_key = root / ".age-key"
            encrypted_env = root / ".env.sops"
            age_key.write_bytes(b"test key fixture; helper must not read it")
            encrypted_env.write_bytes(b"opaque encrypted fixture")
            encrypted_env.chmod(0o600)
            before = encrypted_env.stat()
            contents_before = encrypted_env.read_bytes()

            result = subprocess.run(
                ["bash", str(PERMISSION_HELPER), str(age_key), str(encrypted_env)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            after = encrypted_env.stat()
            self.assertEqual(after.st_uid, before.st_uid)
            self.assertEqual(after.st_gid, age_key.stat().st_gid)
            self.assertEqual(stat.S_IMODE(after.st_mode), 0o640)
            self.assertEqual(encrypted_env.read_bytes(), contents_before)


if __name__ == "__main__":
    unittest.main()
