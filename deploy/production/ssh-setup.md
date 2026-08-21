# CI runner → production SSH setup

The OneDev CI runner (cerberus) deploys to production over SSH as the
`kokonut-deploy` user. This document covers generating the key and what
the production host must configure.

## 1. Generate the deploy keypair (on cerberus — already done)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ki-deploy-ed25519 -N "" -C "ki-deploy@cerberus"
```

- Private key: `~/.ssh/ki-deploy-ed25519` (never leaves this host)
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
echo "ssh-ed25519 AAAA... ki-deploy@cerberus" \
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

## 3. Cerberus SSH config

`~/.ssh/config` on cerberus:

```
Host ki-prod
    HostName <PROD_HOST_IP_OR_DNS>
    User kokonut-deploy
    IdentityFile ~/.ssh/ki-deploy-ed25519
    IdentitiesOnly yes
```

Test: `ssh ki-prod 'docker ps'` — should list containers without prompting.

## 4. Scope of the deploy user (intentional limits)

| Can | Cannot |
|---|---|
| docker CLI (full, via group) | sudo |
| read/write `/opt/ki-prod` | touch other services' files |
| restart KI containers | modify sshd/firewall |

Docker-group access is effectively root for containers — acceptable
because the deploy path is script-gated (`DEPLOY_CONFIRM=yes`) and every
deploy takes a pre-checkpoint. If tighter scoping is wanted later,
constrain with a forced command in `authorized_keys`.

## 5. Key rotation

Rotate annually or on any suspicion of compromise:

1. Generate new keypair on cerberus
2. Append new public key to prod `authorized_keys`
3. Test new key: `ssh -i ~/.ssh/ki-deploy-new ki-prod 'docker ps'`
4. Remove old public key from prod `authorized_keys`
5. Delete old private key on cerberus
