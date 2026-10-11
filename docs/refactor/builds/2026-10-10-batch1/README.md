# Batch 1 artifact evidence — 10 October 2026

Both minimal kernel targets built from the same checkout with ClickHouse disabled.
See comparison.json for image identities, file count and digest. Source inventories
and resolved package name/version inventories match across AMD64 and ARM64.
The source digest covers the explicit allowlist in services/core/image_manifest.py;
configuration, credentials, package binaries and runtime data are excluded.
Requirements inventories include copied optional requirements even when not installed.

Evidence was extracted from stopped, private temporary containers, subsequently
removed. No application process or acceptance suite was run. Ruff passed for the
new manifest module. Optional grpc/mqtt manifest refreshes are implemented but those
targets were not rebuilt in this batch. Inputs remain uncommitted; package versions
are not fully locked and matching names/versions do not establish binary parity.

These tags are build candidates, not deployed replacements. Existing API/worker
image remains 78389fb6cf1f05291e89b35ce4f0271e533bbe5403be97a8d77a29cdfc5825f5.
Rollback requires no runtime action; retain existing deployed images and remove the
new tags if discarded. ARM64 build ran under emulation, not on Raspberry Pi hardware.
