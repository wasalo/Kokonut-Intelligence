"""Durable scheduler contract retaining atomic claim and execution ownership."""

from __future__ import annotations

from typing import Protocol


class SchedulerBackend(Protocol):
    @property
    def worker_id(self) -> str: ...

    def tick(self) -> dict[str, int]: ...

    def get_status(self) -> dict: ...
