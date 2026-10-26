# GitHub Actions → production SSH setup

The GitHub Actions production workflow deploys over SSH as the
`kokonut-deploy` user. Store its private key and the production host key in
the protected GitHub `production` environment; do not put either value in
the repository.

## 1. Generate the deploy keypair

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ki-deploy-ed25519 -N "" -C "ki-deploy@github-actions"
```

- Private key: add as the `DEPLOY_PROD_SSH_KEY` environment secret
- Public key: printed below — copy into the production host's
  `authorized_keys` during provisioning

Print the public key:

```bash
cat ~/.ssh/ki-deploy-ed25519.pub
```

## 2. Production host configuration (run during provisioning)

As root on the production host:

```bash
useradd -m -s /bin/bash kokonut-deploy
usermod -aG docker kokonut-deploy
install -d -m 700 -o kokonut-deploy -g kokonut-deploy /home/kokonut-deploy/.ssh
echo "ssh-ed25519 AAAA... ki-deploy@github-actions" \
  > /home/kokonut-deploy/.ssh/authorized_keys   # paste actual key
chmod 600 /home/kokonut-deploy/.ssh/authorized_keys
chown -R kokonut-deploy:kokonut-deploy /home/kokonut-deploy/.ssh
```

`/etc/ssh/sshd_config` hardening (verify):

```
PasswordAuthentication no          # or at least: Match User kokonut-deploy
AllowUsers ... kokonut-deploy      # if AllowUsers is in use
```

Then `systemctl reload ssh`.

## 3. GitHub environment configuration

Create the `production` environment and configure required reviewers before
using it. Add these values to that environment:

- Variable `DEPLOY_PROD_HOST`: production DNS name or IPv4 address
- Secret `DEPLOY_PROD_SSH_KEY`: private key from step 1
- Secret `DEPLOY_PROD_KNOWN_HOSTS`: verified `known_hosts` entry for the
  production host, including its key type and public host-key value

The workflow enforces strict host-key checking and does not use `ssh-keyscan`
at deploy time.

## 4. Scope of the deploy user (intentional limits)

| Can | Cannot |
|---|---|
| docker CLI (full, via group) | sudo |
| read/write `/opt/ki-prod` | touch other services' files |
| restart KI containers | modify sshd/firewall |

Docker-group access is effectively root for containers. Keep the deploy key
restricted to this host account and use the protected GitHub environment,
explicit `yes` input, and pre-deploy backup gate.

## 5. Key rotation

Rotate annually or on any suspicion of compromise:

1. Generate a new keypair
2. Append new public key to prod `authorized_keys`
3. Update the `DEPLOY_PROD_SSH_KEY` environment secret and test the production workflow
4. Remove old public key from prod `authorized_keys`
5. Delete the old private key
