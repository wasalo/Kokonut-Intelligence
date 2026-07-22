# Secrets Management with SOPS + age

## Why

Plaintext `.env` files containing database passwords, API keys, and private keys are a security risk:
- Accidentally committed via `git add -A`
- Passed into container configuration and potentially visible through runtime inspection
- No access control (anyone with repo access sees all secrets)
- No audit trail (who changed what, when)

SOPS (Secrets OPerationS) + age encrypts secrets at rest in the repository. Only authorized key holders can decrypt. This does not eliminate plaintext at runtime: decrypted values exist in the shell, editor, subprocess, CI workspace, or container environment when used.

## How It Works

```
.env (local plaintext) → sops -e → .env.sops (encrypted, tracked in git)
                                     ↓
sops -d → plaintext env vars → docker compose / Python / scripts
```

- SOPS uses **envelope encryption**: your secrets are encrypted with a random data key, and that data key is encrypted with your age public key
- Only people with the corresponding private key can decrypt
- Adding/removing team members requires changing the recipient list and running `sops updatekeys`; secrets do not need to be retyped, but the encrypted file metadata must be updated

The repository currently has one development age recipient in `.sops.yaml`. Production, team-member, and CI recipients are commented future configuration until an operator adds real public keys.

## Setup

### 1. Install Tools

```bash
# macOS
brew install age sops

# Linux (Debian/Ubuntu)
sudo apt-get install age
sudo snap install sops

# Linux (Arch)
sudo pacman -S age sops
```

### 2. Generate Key Pair

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

Output:
```
Public key: age1abc123...
```

**Back up the private key** (`~/.config/sops/age/keys.txt`) in a password manager. If lost, encrypted secrets are irrecoverable.

### 3. Share Your Public Key

Send your public key (`age1abc123...`) to the team lead. They add it to `.sops.yaml`:

```yaml
creation_rules:
  - path_regex: '\.env(\.sops)?$'
    age: age1_dev_key,age1_server_key,age1_new_person_key
```

Only public age recipients belong in `.sops.yaml`. Never add a private key, decrypted value, or `keys.txt` content.

### 4. Update `.sops.yaml` (one-time)

The team lead runs:

```bash
sops updatekeys .env.sops
```

This re-wraps the data key for the configured recipients. No secret values need to be retyped, but the updated encrypted file must be committed and distributed.

## Daily Operations

### Decrypt and run docker compose

```bash
# Decrypt in memory, export env vars, and start Compose
source scripts/load-secrets.sh
docker compose up -d

# Run commands with secrets available in the current shell
docker compose ps
docker compose logs database
```

`scripts/load-secrets.sh` requires `.env.sops`, verifies that `sops` is installed, sets `SOPS_AGE_KEY_FILE` automatically when `~/.config/sops/age/keys.txt` exists, decrypts to stdout, and exports the parsed dotenv values into the current shell. It does not write a plaintext `.env` file and must be sourced rather than executed in a child shell.

The repository's seed, health-check, schema-snapshot, and Metabase scripts support `.env.sops` first and fall back to `.env`. `scripts/backup.sh` is stricter: it refuses to source a plaintext `.env`.

### Decrypt to stdout (read secrets)

```bash
# View decrypted .env
sops -d --input-type dotenv --output-type dotenv .env.sops

# View a specific variable
sops -d --input-type dotenv --output-type dotenv .env.sops | grep POSTGRES_PASSWORD
```

### Edit secrets

```bash
# Opens $EDITOR with decrypted content, re-encrypts on save
sops .env.sops
```

The editor receives decrypted content. Configure the editor to avoid swap files, backups, shell history, or crash dumps containing secrets, and remove any plaintext working copy after encrypting it.

### Run shell scripts with secrets

```bash
# Source secrets into current shell before running scripts
source scripts/load-secrets.sh
./scripts/seed.sh
./scripts/backup.sh
```

### Python services

Python services that use `services.common.env.load_dotenv()` prefer `.env.sops` and decrypt it through the `sops` CLI. If SOPS is missing, decryption fails, or the encrypted file is absent, the loader falls back to `.env` when present. This fallback is deliberate compatibility behavior, so a failed SOPS decrypt must not be mistaken for a secure successful load.

The loader is idempotent and uses `os.environ.setdefault`, so already-exported variables are not overwritten by dotenv values.

## Team Management

### Add a team member

1. They generate a key: `age-keygen -o ~/.config/sops/age/keys.txt`
2. They share their public key
3. Add it to `.sops.yaml`
4. Push the change
5. An authorized maintainer runs: `sops updatekeys .env.sops`
6. Commit the updated `.env.sops`; the new member can decrypt only after receiving the updated file.

### Remove a team member

1. Remove their key from `.sops.yaml`
2. Run: `sops updatekeys .env.sops`
3. Commit the updated `.env.sops`; the removed key can no longer decrypt the updated file, although it may still decrypt older copies.

### Rotate keys

```bash
# Generate new key pair
age-keygen -o ~/.config/sops/age/keys.txt

# Update .sops.yaml with new public key
# Re-wrap the encrypted data key for the new recipient set
sops updatekeys .env.sops
```

If a private age key may have been compromised, rotate every secret value protected by that key in addition to rotating recipients. Removing the recipient alone does not invalidate plaintext or older encrypted copies.

## CI/CD

The repository does not currently contain a CI workflow that decrypts `.env.sops`; the following is illustrative only. Prefer a platform secret store and ephemeral runners. If a plaintext dotenv file is created, restrict its permissions and delete it in an always-run cleanup step.

### GitHub Actions

```yaml
- name: Decrypt secrets
  env:
    SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
  run: |
    umask 077
    trap 'rm -f .env' EXIT
    sops -d --input-type dotenv --output-type dotenv .env.sops > .env

- name: Deploy
  run: docker compose up -d

- name: Remove plaintext environment
  if: always()
  run: rm -f .env
```

### Jenkins / GitLab CI

Store the private key content as a CI secret, write it to a temporary file, and clean both files on exit:

```bash
umask 077
KEY_FILE=$(mktemp)
trap 'rm -f "$KEY_FILE" .env' EXIT
printf '%s' "$SOPS_AGE_KEY" > "$KEY_FILE"
export SOPS_AGE_KEY_FILE="$KEY_FILE"
sops -d --input-type dotenv --output-type dotenv .env.sops > .env
```

Do not print decrypted output in CI logs. Ensure the CI secret is masked and the temporary workspace is destroyed after the job.

## Production Server Setup

```bash
# Install tools according to the pinned/approved release process
apt-get install -y age
curl -LO https://github.com/getsops/sops/releases/latest/download/sops-v3.13.2.linux.amd64
install -m 0755 sops-v3.13.2.linux.amd64 /usr/local/bin/sops

# Generate server key
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt

# Share only the public key with an authorized maintainer and add it to .sops.yaml
# Then run `sops updatekeys .env.sops` from an authorized workstation.
# Then deploy:
source scripts/load-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Worker overlay

```bash
source scripts/load-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.worker.yml up -d
```

### Cron jobs

```crontab
# Old:
# source /path/to/.env && docker compose ...

# New:
source /path/to/scripts/load-secrets.sh
docker compose ...
```

## Troubleshooting

### "no matching creation rules found"

Your `.sops.yaml` regex doesn't match the file being encrypted. Ensure `path_regex` matches `.env` or `.env.sops`.

### "failed to load age identities"

SOPS can't find your private key. Check:
1. Key exists: `ls -la ~/.config/sops/age/keys.txt`
2. Set the key explicitly when needed: `export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt`
3. On macOS, the SOPS CLI may also use `~/Library/Application Support/sops/age/keys.txt`, but `load-secrets.sh` only auto-selects the `~/.config` path.

### "error loading config"

SOPS can't find `.sops.yaml`. Ensure it's in the project root or a parent directory.

### Decrypt works but docker compose doesn't see variables

Source `scripts/load-secrets.sh` in the shell that launches Docker Compose so the decrypted variables are exported to the child process.

### Python silently uses `.env`

`services/common/env.py` falls back to `.env` when SOPS is unavailable or decryption fails. Remove or secure the plaintext fallback, install/configure SOPS and the correct age identity, and verify that the intended encrypted file can be decrypted before starting services.

### Loader reports `.env.sops.example` missing

The repository does not currently ship `.env.sops.example`. Create a local plaintext `.env` from `.env.example`, fill it with local values, encrypt it to `.env.sops`, then remove the plaintext file:

```bash
cp .env.example .env
# Edit .env with local values, then:
sops -e .env > .env.sops
rm -f .env
```

## Security Model

| Threat | Mitigation |
|--------|------------|
| Secret leaked in git | Encrypted values only — useless without private key |
| Runtime inspection exposes secrets | Encryption at rest does not protect runtime environment values; restrict host/container access and use platform secret injection where available |
| Team member leaves | Remove their key from `.sops.yaml`, run `sops updatekeys` |
| Private key compromised | Generate new key, update `.sops.yaml`, re-encrypt |
| Accidental plaintext file | Keep `.env` ignored, remove temporary plaintext copies, and prefer `source scripts/load-secrets.sh` |
| SOPS decrypt failure | Do not treat a `.env` fallback as secure; repair the key/configuration and rotate if compromise is suspected |
| Editor swap files leak secrets | Configure editor swap/backup behavior and inspect cleanup paths |
| Backup contents leak | `scripts/backup.sh` encrypts database dumps and requires `BACKUP_ENCRYPTION_KEY` |

SOPS protects repository secrets at rest; it is not a substitute for host access control, container hardening, CI secret masking, key rotation, or runtime secret-management infrastructure.

## Files

| File | Purpose | Tracked in Git |
|------|---------|----------------|
| `.sops.yaml` | SOPS recipient config (public keys only) | Yes |
| `.env.sops` | Encrypted secrets file | Yes |
| `scripts/load-secrets.sh` | Helper to decrypt + export env vars | Yes |
| `services/common/env.py` | Python SOPS-first dotenv loader with plaintext fallback | Yes |
| `.env.example` | Placeholder configuration template; never fill with real secrets | Yes |
| `~/.config/sops/age/keys.txt` | Your private key | **Never** |
| `.env` | Plaintext secrets (legacy fallback) | No (gitignored) |

`.env.local` and `.env.*.local` are also ignored. `*.agekey`, `keys.txt`, private-key patterns, `secrets.json`, and key/certificate directories are ignored by `.gitignore`. Verify `git status` and tracked-file scans before committing.

## Source References

- SOPS recipients: `.sops.yaml`
- Ignore policy: `.gitignore`
- Shell loader: `scripts/load-secrets.sh`
- Python loader: `services/common/env.py`
- Backup enforcement: `scripts/backup.sh`
- Placeholder variables: `.env.example`
