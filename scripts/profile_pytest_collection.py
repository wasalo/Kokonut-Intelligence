from __future__ import annotations

import argparse
import os
import resource
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


def _shard_files(*, shard_count: int, shard_number: int) -> list[str]:
    if not 1 <= shard_number <= shard_count:
        raise ValueError("shard_number must be within the requested shard count")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/pytest_test_sharding.py"),
            "--repository-root",
            str(ROOT),
            "--test-root",
            str(ROOT / "tests"),
            "--shard-count",
            str(shard_count),
            "--shard-index",
            str(shard_number - 1),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def _address_space_limiter(limit_mib: int) -> Callable[[], None]:
    def apply_limit() -> None:
        limit_bytes = limit_mib * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))

    return apply_limit


def _rss_kib(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, PermissionError, ValueError):
        return None
    return None


def _cgroup_directory() -> Path | None:
    try:
        lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        _, separator, relative_path = line.partition("::")
        if separator:
            directory = Path("/sys/fs/cgroup") / relative_path.lstrip("/")
            if directory.is_dir():
                return directory
    fallback = Path("/sys/fs/cgroup")
    return fallback if fallback.is_dir() else None


def _memory_snapshot(pid: int, *, process_label: str) -> list[str]:
    result: list[str] = []
    rss = _rss_kib(pid)
    if rss is not None:
        result.append(f"{process_label}_rss_kib={rss}")
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:")):
                key, _, value = line.partition(":")
                result.append(f"host_{key.strip().lower()}={value.strip()}")
    except OSError:
        pass
    directory = _cgroup_directory()
    if directory is not None:
        for name in ("memory.current", "memory.max", "memory.peak", "memory.events", "memory.pressure"):
            try:
                value = (directory / name).read_text(encoding="utf-8").strip().replace("\n", ";")
            except OSError:
                continue
            result.append(f"cgroup_{name.replace('.', '_')}={value}")
    return result


def _run_probe(
    *,
    label: str,
    files: list[str],
    address_space_limit_mib: int,
    python_args: list[str] | None = None,
) -> int:
    if python_args is None:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            "--collect-only",
            "-p",
            "no:cacheprovider",
            *files,
        ]
        probe_type = f"{len(files)} file(s)"
    else:
        command = [sys.executable, *python_args]
        probe_type = "Python command"
    print(f"=== Collection probe: {label} ({probe_type}) ===", flush=True)
    print(f"address_space_limit_mib={address_space_limit_mib}", flush=True)
    print("before: " + " ".join(_memory_snapshot(os.getpid(), process_label="profiler")), flush=True)
    peak_rss_kib = 0
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=_address_space_limiter(address_space_limit_mib),
        )
        started_at = time.monotonic()
        last_heartbeat = 0.0
        rss = _rss_kib(process.pid)
        if rss is not None:
            peak_rss_kib = rss
        while process.poll() is None:
            rss = _rss_kib(process.pid)
            if rss is not None:
                peak_rss_kib = max(peak_rss_kib, rss)
            elapsed = time.monotonic() - started_at
            if elapsed - last_heartbeat >= 1:
                snapshot = " ".join(_memory_snapshot(process.pid, process_label="pytest"))
                print(
                    f"heartbeat label={label} elapsed_seconds={elapsed:.1f} "
                    f"peak_rss_kib={peak_rss_kib} {snapshot}",
                    flush=True,
                )
                last_heartbeat = elapsed
            time.sleep(0.25)
        exit_code = process.wait()
        final_rss = _rss_kib(process.pid)
        if final_rss is not None:
            peak_rss_kib = max(peak_rss_kib, final_rss)
        output.seek(0)
        tail = deque(output, maxlen=35)
    print(f"probe_exit_code={exit_code} peak_rss_mib={peak_rss_kib / 1024:.1f}", flush=True)
    print("after: " + " ".join(_memory_snapshot(os.getpid(), process_label="profiler")), flush=True)
    if tail:
        print("--- probe output tail ---")
        print("".join(tail), end="", flush=True)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile collection memory for one deterministic pytest shard.")
    parser.add_argument("--shard-count", type=int, default=96)
    parser.add_argument("--shard-number", type=int, default=55)
    parser.add_argument("--address-space-limit-mib", type=int, default=8192)
    arguments = parser.parse_args()
    if sys.platform != "linux":
        parser.error("collection profiling requires Linux /proc and cgroup telemetry")
    if arguments.shard_count < 1 or arguments.address_space_limit_mib < 1:
        parser.error("shard count and address-space limit must be positive")

    files = _shard_files(shard_count=arguments.shard_count, shard_number=arguments.shard_number)
    if not files:
        parser.error("selected shard has no test files")
    print(
        f"Profiling shard {arguments.shard_number}/{arguments.shard_count} "
        f"with {len(files)} files under a capped address space.",
        flush=True,
    )
    for test_file in files:
        _run_probe(
            label=f"single:{test_file}",
            files=[test_file],
            address_space_limit_mib=arguments.address_space_limit_mib,
        )

    import_probes = (
        ("indexer-only", "from services.guilds.indexer import KGPIndexer"),
        (
            "worker-test-module-import",
            "import runpy\n"
            "runpy.run_path('tests/test_kgp_worker_durability.py')\n",
        ),
        (
            "worker-test-import-order",
            "from unittest.mock import MagicMock, call, patch\n"
            "import pytest\n"
            "from services.guilds.indexer import KGPIndexer\n",
        ),
        (
            "service-test-import-order",
            "from eth_abi import encode\n"
            "from web3 import Web3\n"
            "from services.guilds.indexer import EVENT_TOPICS, KGP_EVENT_NAMES, decode_log\n"
            "from services.guilds.kgp import build_claim_voucher, claim_typed_data, compute_award_id\n",
        ),
    )
    for label, source in import_probes:
        _run_probe(
            label=f"importtime:{label}",
            files=[],
            address_space_limit_mib=arguments.address_space_limit_mib,
            python_args=["-X", "importtime", "-c", source],
        )
    _run_probe(
        label="importtime:pytest-worker-collection",
        files=[],
        address_space_limit_mib=arguments.address_space_limit_mib,
        python_args=[
            "-X",
            "importtime",
            "-m",
            "pytest",
            "-v",
            "--collect-only",
            "-p",
            "no:cacheprovider",
            "tests/test_kgp_worker_durability.py",
        ],
    )

    _run_probe(
        label="pytest-worker-collection-assert-plain",
        files=[],
        address_space_limit_mib=arguments.address_space_limit_mib,
        python_args=[
            "-m",
            "pytest",
            "-v",
            "--collect-only",
            "--assert=plain",
            "-p",
            "no:cacheprovider",
            "tests/test_kgp_worker_durability.py",
        ],
    )

    _run_probe(
        label="pytest-worker-collection-no-unittest-plugin",
        files=[],
        address_space_limit_mib=arguments.address_space_limit_mib,
        python_args=[
            "-m",
            "pytest",
            "-v",
            "--collect-only",
            "-p",
            "no:unittest",
            "-p",
            "no:cacheprovider",
            "tests/test_kgp_worker_durability.py",
        ],
    )

    _run_probe(
        label="pytest-worker-collection-no-external-plugins",
        files=[],
        address_space_limit_mib=arguments.address_space_limit_mib,
        python_args=[
            "-m",
            "pytest",
            "-v",
            "--collect-only",
            "--assert=plain",
            "-p",
            "no:anyio",
            "-p",
            "no:platformdirs",
            "-p",
            "no:unittest",
            "-p",
            "no:cacheprovider",
            "tests/test_kgp_worker_durability.py",
        ],
    )

    group_exit = _run_probe(
        label="complete-shard",
        files=files,
        address_space_limit_mib=arguments.address_space_limit_mib,
    )
    if group_exit != 0:
        for prefix_size in range(2, len(files)):
            prefix_exit = _run_probe(
                label=f"sorted-prefix:{prefix_size}",
                files=files[:prefix_size],
                address_space_limit_mib=arguments.address_space_limit_mib,
            )
            if prefix_exit != 0:
                print(
                    f"First failing sorted prefix: {prefix_size} files; "
                    f"last file={files[prefix_size - 1]}",
                    flush=True,
                )
                break
    print("Collection profiling completed; probe exit codes are diagnostic and do not change the CI gate.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
