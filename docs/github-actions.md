# GitHub Actions operations

GitHub is the canonical Git and automation platform for Kokonut Intelligence.
The former OneDev buildspec has been replaced by these repository workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| `CI` | Pull requests to `main`, pushes to `main`, manual dispatch | Runs secret-pattern and image-digest gates, the locked AMD64/ARM64 image builds, Python security checks and full suite, static analysis, Solidity checks, and Directus hook checks. It builds temporary OCI archives only; it does not publish images. |
| `Security` | Pull requests to `main`, pushes to `main`, weekly schedule, manual dispatch | Scans tracked source and all fetched Git history with the checksum-pinned Gitleaks CLI. |
| `Deploy staging` | Manual dispatch from `main` only | Requires the explicit `yes` input and protected `staging` environment; a source-controlled disabled flag keeps deployment blocked until the architecture/data hold is cleared. |
| `Deploy production` | Manual dispatch from `main` only | Requires the explicit `yes` input, the protected `production` environment, pre-deploy backup, and post-deploy health verification. |

Every third-party action is pinned to a full commit SHA. The CI job is limited
to 90 minutes, uses the isolated `ki-ci` Compose project and high loopback
ports, installs Foundry from a SHA-pinned action at a fixed release, and tears
its containers and volumes down when it exits.

## GitHub repository settings

After the workflows are merged:

1. Enable GitHub Actions for the repository.
2. Protect `main` and require the `CI / ci` and `Security / gitleaks` checks
   before merging. Require a pull request and review according to the
   repository's governance policy.
3. Create a `staging` environment and register a repository-scoped Linux x64
   self-hosted runner on the staging host with the label `ki-staging`. The
   runner account needs Docker access and the existing `/opt/ki-staging`
   checkout, age key, and encrypted environment. Set that checkout's `origin`
   to `https://github.com/wasalo/Kokonut-Intelligence.git`. Keep the runner
   updated to version 2.327.1 or newer and never target it from pull-request
   workflows. Keep staging deployment manual until the architecture and data
   gates are cleared.
4. Create a `production` environment with required reviewers. Set its
   `DEPLOY_PROD_HOST` variable to the production DNS name or IPv4 address.
   Add `DEPLOY_PROD_SSH_KEY` as the private key secret and
   `DEPLOY_PROD_KNOWN_HOSTS` as the verified SSH host-key entry. The private
   key must be authorized for the `kokonut-deploy` user on the production host.

The staging host keeps its existing SOPS age identity and encrypted
environment. The production host also keeps its own separate SOPS identity.
Neither age identity nor decrypted deployment environment is copied into
GitHub Actions secrets.

The CI and Security workflows need no deployment credentials. Their
`GITHUB_TOKEN` permissions are read-only. The Security workflow runs the
upstream Gitleaks CLI directly; it does not require a Gitleaks Action license,
write PR comments, or upload scan reports. Its checked-in `.gitleaks.toml`
extends the default rules and records narrow, rule-specific exceptions for
public EVM addresses, vendored OpenZeppelin test fixtures, source/recovery
hash inventories, deterministic test identifiers, and documented credential
placeholders. Full Git history remains in scope, and every unallowlisted match
still fails the job.

## Deployment controls

Staging deployment is intentionally paused behind a manual workflow dispatch.
It is currently blocked by `DEPLOY_STAGING_ENABLED: 'no'` in the workflow.
After the architecture and legacy-data gates clear, enable it in a reviewed
pull request, then dispatch from `main`, choose `yes`, and satisfy the
`staging` environment review. It uses the dedicated `ki-staging` runner,
updates the host checkout from the canonical GitHub origin, and calls the
existing idempotent staging deployment script.

Production is never automatic. Dispatch the workflow from `main`, choose
`yes`, and satisfy the `production` environment review gate. The deployment
script changes the production checkout origin to GitHub, takes a backup before
updating containers, checks health, and leaves rollback as an explicit human
decision.

The repository cannot create GitHub runner registrations, environments,
required reviewers, branch rules, or secrets. Those settings are listed above
for the repository owner to apply after merge. Once GitHub CI and Security run
successfully and deployment settings are configured, retire any remaining
OneDev-side triggers or runner service. The tracked OneDev buildspec has been
removed.
