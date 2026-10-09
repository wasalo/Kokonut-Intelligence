# KI Production — bootstrap runbook

Production runs on a dedicated VPS managed via Coolify (Traefik for TLS).
This runbook takes a fresh host to a deployed, healthy KI production stack.

**Everything else is already built** — deploy scripts, CI promotion job,
backup policy. This document covers the one-time host provisioning.

## Prerequisites

- A VPS (Wasabi provisions; recommend 4 vCPU / 8 GB minimum — ClickHouse
  alone wants 4G)
- DNS: `kokonut.network` + `metabase.kokonut.network` A records → host IP
  (or Cloudflare-proxied)
- SSH access as root during provisioning

## 1. Base host setup

```bash
apt-get update && apt-get upgrade -y
apt-get install -y docker.io docker-compose-plugin git curl ca-certificates
# Coolify (if using it for Traefik management):
#   curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

## 2. Create the deploy user

```bash
useradd -m -s /bin/bash kokonut-deploy
usermod -aG docker kokonut-deploy        # docker access, no sudo
mkdir -p /home/kokonut-deploy/.ssh
chmod 700 /home/kokonut-deploy/.ssh
```

Authorize the CI runner's key (public key generated on cerberus — see
`ssh-setup.md`):

```bash
echo "ssh-ed25519 AAAA... ki-deploy@cerebus" \
  > /home/kokonut-deploy/.ssh/authorized_keys
chmod 600 /home/kokonut-deploy/.ssh/authorized_keys
chown -R kokonut-deploy:kokonut-deploy /home/kokonut-deploy/.ssh
```

## 3. Checkout + secrets

```bash
sudo -u kokonut-deploy git clone \
  https://git.kokonut.network/Kokonut-Intelligence /opt/ki-prod
cd /opt/ki-prod

# age keypair for production secrets (NEVER reuse staging's)
age-keygen -o /opt/ki-prod/.age-key && chmod 600 /opt/ki-prod/.age-key
age-keygen -y /opt/ki-prod/.age-key   # public key → put in .sops.yaml

# Create .sops.yaml with the prod public key, then:
cp deploy/production/.env.production.example deploy/production/.env.production
# edit: fill all replace-with-strong-* values
cd deploy/production && sops -e -i .env.production && rm -f .env.production
git add .sops.yaml .env.production.sops
git commit -m "chore(prod): production secrets"
git push origin main   # or push to a branch and merge via PR
```

## 4. First deployment

From cerberus (CI runner):

```bash
DEPLOY_PROD_HOST=ki-prod DEPLOY_CONFIRM=yes \
  deploy/scripts/deploy-production.sh
```

The script: backs up (no-op checkpoint on first run), pulls, composes up
with `docker-compose.prod.yml` + `traefik.yml`, verifies health.

## 5. Post-deploy verification

- [ ] `https://kokonut.network` serves Directus login over valid TLS
- [ ] `https://metabase.kokonut.network` serves Metabase
- [ ] Gateway health: `curl https://kokonut.network/health`
- [ ] `PUBLIC_RESTRICT=true` confirmed: unauthenticated data endpoints return 401/403
- [ ] Backups: first nightly checkpoint appears in `/opt/ki-prod/backups`
- [ ] OneDev `deploy-production` promotion job tested (dry-run shape)

## 6. Go-live data ingestion

Once verified, ingest the historical Kokonut data per the data team's
plan. **Do not skip the backup verification step before ingesting** —
the first real backup must exist and restore-test clean before the
database holds irreplaceable data.
