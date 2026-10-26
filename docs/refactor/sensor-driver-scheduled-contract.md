# Scheduled sensor-driver contract

Scheduled sensor pulls accept only source-controlled driver implementations
whose registered name, type, module, and class match the code allowlist in
`services/drivers/registry.py`. Every scheduled driver must implement
`fetch_scheduled`; the database registry cannot select an import target or
replace the safe scheduled fetch behavior. Manual driver and CSV CLI operations
remain separate operator paths.

The built-in `sensor_csv` driver reads only beneath
`/var/lib/kokonut/sensor-inputs` in worker containers. Compose mounts the host
directory selected by `KOKONUT_SENSOR_CSV_HOST_DIR` (default
`./data/sensor-inputs`) read-only. A persisted `driver_instance.config.file_path`
may be relative to that root or an absolute path beneath it. Scheduled reads
reject missing configuration, paths outside the root, parent traversal,
symlinked path components, and non-regular files. The descriptor walk uses
`O_NOFOLLOW` for the root, each directory, and the file, so replacing a path
with a symlink between validation and open does not escape the mount.

For direct host execution, set `KOKONUT_SENSOR_CSV_ROOT` to the input directory.
For Compose workers, the in-container root is fixed and the host directory is
configurable through `KOKONUT_SENSOR_CSV_HOST_DIR`. Keep the host directory
readable to the container's worker user and place only intended sensor input
files there.

This closes scheduled code-selection and filesystem-root boundaries only. The
scheduled sensor path still uses the shared runtime database identity and
direct table access; the signed worker principal, bounded SQL functions, RLS,
provider/runtime parity, and live schedule reconciliation remain open. Do not
infer tenant authorization from the location and driver UUIDs.
