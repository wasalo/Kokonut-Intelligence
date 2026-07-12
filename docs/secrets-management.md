# Secrets Management with SOPS + age

## Why

Plaintext `.env` files containing database passwords, API keys, and private keys are a security risk:
- Accidentally committed via `git add -A`
- Visible to all container processes via `docker inspect`
- No access control (anyone with repo access sees all secrets)
- No audit trail (who changed what, when)

SOPS (Secrets OPerationS) + age solves this by encrypting the `.env` file in the repo. Only authorized key holders can decrypt. Plaintext never touches disk.

## How It Works

```
.env (plaintext) → sops -e → .env.sops (encrypted, tracked in git)
                                    ↓
sops -d → plaintext env vars → docker compose / Python / scripts
```

- SOPS uses **envelope encryption**: your secrets are encrypted with a random data key, and that data key is encrypted with your age public key
- Only people with the corresponding private key can decrypt
- Adding/removing team members = adding/removing public keys (no re-encryption needed)

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

### 4. Update `.sops.yaml` (one-time)

The team lead runs:

```bash
sops updatekeys .env.sops
```

This re-encrypts the data key to include the new recipient. No secrets need re-typing.

## Daily Operations

### Decrypt and run docker compose

```bash
# Decrypt in memory, inject as env vars for the command
sops exec-env .env.sops docker compose up -d

# Run any command with secrets available
sops exec-env .env.sops docker compose ps
sops exec-env .env.sops docker compose logs database
```

### Decrypt to stdout (read secrets)

```bash
# View decrypted .env
sops -d .env.sops

# View a specific variable
sops -d .env.sops | grep POSTGRES_PASSWORD
```

### Edit secrets

```bash
# Opens $EDITOR with decrypted content, re-encrypts on save
sops .env.sops
```

### Run shell scripts with secrets

```bash
# Source secrets into current shell
source scripts/load-secrets.sh

# Or use exec-env for any script
sops exec-env .env.sops ./scripts/seed.sh
sops exec-env .env.sops ./scripts/backup.sh
```

### Python services

Python services automatically detect `.env.sops` and decrypt via `services/common/env.py`. No command changes needed.

## Team Management

### Add a team member

1. They generate a key: `age-keygen -o ~/.config/sops/age/keys.txt`
2. They share their public key
3. Add it to `.sops.yaml`
4. Push the change
5. They run: `sops updatekeys .env.sops`

### Remove a team member

1. Remove their key from `.sops.yaml`
2. Run: `sops updatekeys .env.sops`
3. The removed key can no longer decrypt

### Rotate keys

```bash
# Generate new key pair
age-keygen -o ~/.config/sops/age/keys.txt

# Update .sops.yaml with new public key
# Re-encrypt
sops updatekeys .env.sops
```

## CI/CD

### GitHub Actions

```yaml
- name: Decrypt secrets
  env:
    SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
  run: sops -d .env.sops > .env

- name: Deploy
  run: docker compose up -d
```

Or use `exec-env` directly:

```yaml
- name: Deploy with secrets
  env:
    SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
  run: sops exec-env .env.sops docker compose up -d
```

### Jenkins / GitLab CI

Store the private key content as a CI secret, write it to a temp file:

```bash
echo "$SOPS_AGE_KEY" > /tmp/age-key.txt
chmod 600 /tmp/age-key.txt
export SOPS_AGE_KEY_FILE=/tmp/age-key.txt
sops -d .env.sops > .env
```

## Production Server Setup

```bash
# Install tools
apt-get install -y age
curl -LO https://github.com/getsops/sops/releases/latest/download/sops-v3.13.2.linux.amd64
install -m 0755 sops-v3.13.2.linux.amd64 /usr/local/bin/sops

# Generate server key
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt

# Share public key with team lead (add to .sops.yaml)
# Then deploy:
sops exec-env .env.sops docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Worker overlay

```bash
sops exec-env .env.sops docker compose -f docker-compose.yml -f docker-compose.worker.yml up -d
```

### Cron jobs

```crontab
# Old:
# source /path/to/.env && docker compose ...

# New:
sops exec-env /path/to/.env.sops docker compose ...
```

## Troubleshooting

### "no matching creation rules found"

Your `.sops.yaml` regex doesn't match the file being encrypted. Ensure `path_regex` matches `.env` or `.env.sops`.

### "failed to load age identities"

SOPS can't find your private key. Check:
1. Key exists: `ls -la ~/.config/sops/age/keys.txt`
2. On macOS, SOPS also looks in `~/Library/Application Support/sops/age/keys.txt`
3. Or set: `export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt`

### "error loading config"

SOPS can't find `.sops.yaml`. Ensure it's in the project root or a parent directory.

### Decrypt works but docker compose doesn't see variables

Ensure you're running `sops exec-env .env.sops docker compose ...` as a single command (not in separate steps).

## Security Model

| Threat | Mitigation |
|--------|------------|
| Secret leaked in git | Encrypted values only — useless without private key |
| `docker inspect` exposes secrets | `exec-env` sets env vars in memory, not in container config |
| Team member leaves | Remove their key from `.sops.yaml`, run `sops updatekeys` |
| Private key compromised | Generate new key, update `.sops.yaml`, re-encrypt |
| Accidental `sops -d .env.sops > .env` | Never write plaintext to disk — use `exec-env` |
| Editor swap files leak secrets | SOPS edits in memory; warn about editor behavior |

## Files

| File | Purpose | Tracked in Git |
|------|---------|----------------|
| `.sops.yaml` | SOPS recipient config (public keys only) | Yes |
| `.env.sops` | Encrypted secrets file | Yes |
| `scripts/load-secrets.sh` | Helper to decrypt + export env vars | Yes |
| `~/.config/sops/age/keys.txt` | Your private key | **Never** |
| `.env` | Plaintext secrets (legacy fallback) | No (gitignored) |
