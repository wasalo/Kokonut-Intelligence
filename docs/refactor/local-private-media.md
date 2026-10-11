# Encrypted local private field media

`PrivateMediaStore` in `services/mobile/media_storage.py` describes the existing
upload, metadata-check, and cleanup contract. S3 remains the default provider.
Explicit `MOBILE_MEDIA_PROVIDER=local` selects `services/mobile/local_media.py`;
unknown providers fail configuration. Local selection requires no S3 settings.

Local configuration requires an absolute dedicated directory owned by the app
with mode 0700 and `MOBILE_MEDIA_LOCAL_KEY`, a random 32-byte key encoded as hex.
Missing/invalid keys fail before directory creation. Keep this key encrypted in
SOPS and inject it into the runtime; it is not generated automatically or logged.
The local driver requires PyCryptodome, now an explicit dependency (previously
already installed transitively by Web3 in the candidate).

Files use AES-256-GCM with fresh random 12-byte nonces and 16-byte authentication
tags. The object key and envelope version are authenticated associated data.
The API follows the library's documented authenticated-encryption methods:
[PyCryptodome GCM](https://www.pycryptodome.org/src/cipher/modern#gcm-mode).
Object filenames are hashes of validated private virtual keys; no user-supplied
path is used as a filesystem path. Writes use private temporary files, fsync,
and exclusive hard-link publication so existing objects are never overwritten.
Reads reject symlinks/non-regular files, bound envelope size, and authenticate
the full object before returning length/type metadata. Deletion is idempotent.

JPEG/type and 2 MB limits remain. Device-token auth, location scoping, upload
hash records, transactional registration, sync verification, and cleanup on
registration rollback stay in the existing mobile API. Files are never mounted
as static assets or given public URLs. This adapter does not add download routes
or bypass existing access checks.

## Adoption and recovery gates

- Prepare a persistent app-owned private directory/volume and inject a distinct
  random encryption key through SOPS; never reuse a database password as the key.
- Validate upload, sync metadata checks, corruption/wrong-key rejection,
  traversal/symlink handling, exclusive-write races, disk failure, and rollback.
- Back up encrypted files and the matching key separately; rehearse recovery
  and verify content hashes against upload records.
- Do not switch an installation containing S3 uploads to local without an
  explicit object migration and reconciliation. The current DB/runtime select
  one provider globally; there is no per-object backend routing or key rotation.
- Recover orphaned temporary/unregistered objects only through reviewed
  reconciliation; crashes between file publication and DB commit can leave them.

Lint, dependency alignment (11 groups / 28 direct requirements), and whitespace
checks passed. Runtime/security and recovery suites remain pending. No key was
created, no evidence copied, and local storage is not enabled in the running
candidate. Rebuild before using this adapter. The old S3 default remains usable.
Rollback removes local selection; preserve files and their key if any local
objects have been written. Do not delete evidence during provider switching.
