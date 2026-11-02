# GitHub Actions operations

GitHub is the canonical Git and automation platform for Kokonut Intelligence.
The former OneDev buildspec has been replaced by these repository workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| `CI` | Pull requests to `develop` or `main`, pushes to `develop` or `main`, manual dispatch | Runs dependency-free preflight, then parallel source/security/static/contract, database-integration, and AMD64/ARM64 Kernel image gates. Stable required check `CI / ci` aggregates every gate. CI builds test images only; it does not publish or deploy them. |
| `Security` | Pull requests to `develop` or `main`, pushes to `develop` or `main`, weekly schedule, manual dispatch | Scans tracked source and all fetched Git history with the checksum-pinned Gitleaks CLI. |
| `Publish Kernel images` | Manual dispatch from `main` with the explicit `publish` input | Publishes digest-pinned AMD64/ARM64 Standard app and OIDC images after the `kernel-release` environment gate; configure required reviewers before first use. It records the image references and does not deploy them. |
| `Deploy staging` | Manual dispatch from `main` only | Requires the explicit `yes` input and protected `staging` environment; a source-controlled disabled flag keeps deployment blocked until the architecture/data hold is cleared. |
| `Deploy production` | Manual dispatch from `main` only | Requires the explicit `yes` input, the protected `production` environment, pre-deploy backup, and post-deploy health verification. |

Every third-party action is pinned to a full commit SHA. CI runs on
GitHub-hosted `ubuntu-24.04`. Preflight has a 10-minute limit; source checks and
multi-architecture image checks each have a 45-minute limit; database
integration has a 90-minute limit. The `integration-ci` job uses the isolated
`ki-ci` Compose project and high loopback ports, installs Foundry from a
SHA-pinned action at a fixed release, and tears its containers and volumes down
when it exits. On failure, source and integration jobs upload separate
diagnostic artifacts retained for seven days. Per-step Actions logs remain the
primary place to find the failure; artifacts are additional context.

## GitHub repository settings

### Current branch ruleset audit — 26 October 2026

The active `Main and develop branch protection` ruleset (ID `18234835`)
targets both `main` and `develop`. It requires a pull request, one approving
review, dismissal of stale approvals after new commits, resolved conversations,
up-to-date branches, protected deletion, no force pushes, and the current status
checks `CI / ci` and `Security / gitleaks`. Its allowed pull-request merge
methods are merge commits, squash, and rebase. The separate
`Develop linear history` ruleset (ID `25924242`) applies only to `develop`, so
feature PRs there must use squash or rebase. `main` permits merge commits for
reviewed release PRs, preserving the ancestry of the long-lived `develop`
integration branch. The repository also enables merge commits in its general
settings. The separate `Version tag protection` ruleset (ID `18234836`) remains
active and unchanged.

The ruleset also requires code-owner review, but there is no first-party
`CODEOWNERS` file in `.github/`, the repository root, or `docs/`. Thus the
setting currently has no meaningful first-party ownership map. Two user bypass
actors (`wasabinetwork` and `wasalo`) are configured as `Always allow`; see the
owner decisions below.

GitHub Actions is enabled. Keep the following operating configuration aligned
with the ruleset:

1. Send feature pull requests to `develop`, using squash or rebase to preserve
   its linear history. Promote completed release batches from `develop` to
   `main` with a separate pull request; use a merge commit when preserving
   release ancestry is desired. Both branches require `CI / ci` and
   `Security / gitleaks`.
2. Create a `staging` environment and register a repository-scoped Linux x64
   self-hosted runner on the staging host with the label `ki-staging`. The
   runner account needs Docker access and the existing `/opt/ki-staging`
   checkout, age key, and encrypted environment. Set that checkout's `origin`
   to `https://github.com/wasalo/Kokonut-Intelligence.git`. Keep the runner
   updated to version 2.327.1 or newer and never target it from pull-request
   workflows. Keep staging deployment manual until the architecture and data
   gates are cleared.
3. Create a `production` environment with required reviewers. Set its
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

#### Ruleset notes and follow-up

- Decide whether both `Always allow` bypass entries are needed. Pull-request-
  only bypass prevents direct pushes by those users but still lets them bypass
  rules through a PR; remove bypass entirely if they should not bypass reviews
  or checks. Keep emergency access an explicit repository-owner decision.
- Add `.github/CODEOWNERS` after maintainers assign accountable owners for
  first-party paths. Until then, the code-owner rule does not establish actual
  file ownership.
- Linear history is enforced only on `develop`. The shared PR rule allows
  merge commits, squash, or rebase on both branches; the `develop`-only linear
  history rule blocks merge commits there. On `main`, a reviewed release PR can
  use a merge commit to preserve ancestry. The two bypass lists are distinct:
  the shared ruleset retains `wasabinetwork` and `wasalo`, while the linear
  history ruleset allows `wasabinetwork` and organization administrators.
  Organization administrators include all current organization owners.
- Merge queue and signed commits are optional. Required reviews, strict checks,
  protected deletion, and blocked force pushes are a sound baseline without
  adding another merge gate or commit-signing key management.

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

The repository cannot create GitHub runner registrations, environment
reviewers, or secrets. Those settings are listed above for the repository
owner to configure. Once deployment settings are configured, retire any
remaining OneDev-side triggers or runner service. The tracked OneDev buildspec
has been removed.
