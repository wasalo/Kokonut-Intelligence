# Legacy Compose production runbook (not the Kernel Standard profile)

This document describes the legacy integration stack only. The current
production target is the Kernel deployment at `hub.kokonut.network`; production
has not passed its deployment and operational acceptance gates. Use the
[current architecture and implementation guide](../../docs/refactor/current-state-and-implementation.md)
for the current profile status.

The `deploy-production.yml` workflow and `deploy/scripts/deploy-production.sh`
still deploy the legacy Compose files (`docker-compose.yml`,
`docker-compose.prod.yml`, and `docker-compose.traefik.yml`). They do not
deploy the Kernel Standard profile. Their presence does not mean the production
host, secret delivery, backups, recovery, or health gates have been accepted.

## Prerequisites

- A VPS sized and secured for the legacy Compose stack (the old resource
  suggestions below are not Kernel sizing guidance)
- Legacy DNS only: `kokonut.network` and `metabase.kokonut.network`; the current
  Kernel application hostname selected by the owner is `hub.kokonut.network`
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

Authorize the GitHub Actions deploy key (see `ssh-setup.md`):

```bash
echo "ssh-ed25519 AAAA... ki-deploy@github-actions" \
  > /home/kokonut-deploy/.ssh/authorized_keys
chmod 600 /home/kokonut-deploy/.ssh/authorized_keys
chown -R kokonut-deploy:kokonut-deploy /home/kokonut-deploy/.ssh
```

## 3. Checkout + secret-delivery gate

```bash
sudo -u kokonut-deploy git clone \
  https://github.com/wasalo/Kokonut-Intelligence.git /opt/ki-prod
cd /opt/ki-prod

# The production workflow does not decrypt or load
# deploy/production/.env.production.sops. The remote Compose invocation also
# needs the required environment at the host; the current workflow does not
# provision it. Secret-delivery wiring is an open release gate.
# Do not follow the ignored sample's SOPS instructions and assume the file is
# consumed. Implement and review secret injection before enabling deployment.
```

## 4. Legacy deployment workflow

From the repository's GitHub Actions page, dispatch
`.github/workflows/deploy-production.yml` from `main`, select `yes`, and
approve the `production` environment if it is configured with required
reviewers. Configure the environment values described in
[GitHub Actions setup](../../docs/github-actions.md).

The script attempts a pre-deployment backup, pulls the selected `main` commit,
and runs the legacy Compose stack with `docker-compose.prod.yml` plus
`docker-compose.traefik.yml`, then checks health. The production host must
already have its required runtime environment available to the root Compose
project; this workflow does not consume `deploy/production/.env.production.sops`.
The runbook has not been accepted as a Kernel production procedure.

## 5. Post-deploy verification

- [ ] Legacy Directus URL and TLS are explicitly approved for any legacy deployment
- [ ] Optional Metabase exposure and its source access are explicitly reviewed
- [ ] Legacy Gateway health path is checked against the selected Caddy/Traefik routes
- [ ] `PUBLIC_RESTRICT=true` confirmed: unauthenticated data endpoints return 401/403
- [ ] Backups: first nightly checkpoint appears in `/opt/ki-prod/backups`
- [ ] GitHub Actions `deploy-production` promotion tested (dry-run shape)

## 6. Legacy data-ingestion caution

Do not ingest owner-held farm data through this legacy runbook. Data migration,
the Kernel profile, backup/restore rehearsal, and cutover require their own
reviewed procedures and rollback evidence before production use.
