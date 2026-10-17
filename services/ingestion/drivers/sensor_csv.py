"""CSV sensor driver — wraps services.ingestion.sensor_ingester CSV path."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from services.drivers.base import BaseDriver

MAX_SENSOR_CSV_RECORDS = 10_000
SCHEDULED_SENSOR_CSV_ROOT_ENV = "KOKONUT_SENSOR_CSV_ROOT"


class Driver(BaseDriver):
    name = "sensor_csv"
    version = "1.0.0"
    driver_type = "sensor"
    supports_scheduled_pull = True

    def validate_config(self, config: dict) -> bool:
        return "file_path" in config

    def discover(self, config: dict) -> list[dict]:
        return [{"source_id": config.get("file_path", ""), "display_name": "CSV file"}]

    def fetch(self, source: dict) -> dict:
        file_path = source.get("source_id", "")
        with open(file_path, "r", newline="", encoding="utf-8") as stream:
            return self.fetch_stream(stream)

    def fetch_scheduled(self, source: dict) -> dict:
        """Read one scheduled CSV using an openat walk beneath the input root.

        Every path component is opened without following symlinks. This keeps
        mutable database configuration from redirecting a worker outside its
        read-only sensor-input mount, including through a symlink replacement
        between path validation and file open.
        """
        file_path = source.get("source_id", "")
        root_value = os.environ.get(SCHEDULED_SENSOR_CSV_ROOT_ENV)
        if not isinstance(root_value, str) or not root_value.strip():
            raise ValueError("scheduled sensor CSV root is not configured")

        try:
            root = Path(root_value).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("scheduled sensor CSV root is unavailable") from None
        if not root.is_dir():
            raise ValueError("scheduled sensor CSV root is not a directory")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("scheduled sensor CSV source is invalid")

        configured_path = Path(file_path).expanduser()
        if ".." in configured_path.parts:
            raise ValueError("scheduled sensor CSV path must stay within its configured root")
        if not configured_path.is_absolute():
            configured_path = root / configured_path
        try:
            absolute_path = Path(os.path.abspath(configured_path))
            relative_path = absolute_path.relative_to(root)
        except (OSError, ValueError):
            raise ValueError("scheduled sensor CSV path must stay within its configured root") from None
        if not relative_path.parts:
            raise ValueError("scheduled sensor CSV source must be a regular file")

        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not getattr(os, "O_DIRECTORY", 0) or not nofollow:
            raise RuntimeError("scheduled sensor CSV safe-open flags are unavailable")

        try:
            directory_fd = os.open(root, directory_flags | nofollow)
        except OSError:
            raise ValueError("scheduled sensor CSV root is unavailable") from None
        current_fd = directory_fd
        file_fd = None
        try:
            for part in relative_path.parts[:-1]:
                next_fd = os.open(
                    part,
                    directory_flags | nofollow,
                    dir_fd=current_fd,
                )
                if current_fd != directory_fd:
                    os.close(current_fd)
                current_fd = next_fd

            file_fd = os.open(
                relative_path.parts[-1],
                os.O_RDONLY | nofollow,
                dir_fd=current_fd,
            )
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise ValueError("scheduled sensor CSV source must be a regular file")
            with os.fdopen(file_fd, "r", newline="", encoding="utf-8") as stream:
                file_fd = None
                return self.fetch_stream(stream)
        except OSError:
            raise ValueError("scheduled sensor CSV source is unavailable") from None
        finally:
            if file_fd is not None:
                os.close(file_fd)
            if current_fd != directory_fd:
                os.close(current_fd)
            os.close(directory_fd)

    @staticmethod
    def fetch_stream(stream) -> dict:
        import csv

        reader = csv.DictReader(stream)
        rows = []
        for row in reader:
            if len(rows) >= MAX_SENSOR_CSV_RECORDS:
                raise ValueError(
                    f"sensor CSV exceeds the {MAX_SENSOR_CSV_RECORDS}-record limit"
                )
            rows.append(row)
        return {"data": rows}

    def transform(self, raw: dict) -> list[dict]:
        return raw.get("data", [])

    def health_check(self, config: dict) -> bool:
        import os
        file_path = config.get("file_path", "")
        return os.path.isfile(file_path) if file_path else False
