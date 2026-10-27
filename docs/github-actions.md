# GitHub Actions operations

GitHub is the canonical Git and automation platform for Kokonut Intelligence.
The former OneDev buildspec has been replaced by these repository workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| `CI` | Pull requests to `develop` or `main`, pushes to `develop` or `main`, manual dispatch | Runs secret-pattern and image-digest gates, the locked AMD64/ARM64 image builds, Python security checks and full suite, static analysis, Solidity checks, and Directus hook checks. It builds temporary OCI archives only; it does not publish images. |
| `Security` | Pull requests to `develop` or `main`, pushes to `develop` or `main`, weekly schedule, manual dispatch | Scans tracked source and all fetched Git history with the checksum-pinned Gitleaks CLI. |
| `Deploy staging` | Manual dispatch from `main` only | Requires the explicit `yes` input and protected `staging` environment; a source-controlled disabled flag keeps deployment blocked until the architecture/data hold is cleared. |
| `Deploy production` | Manual dispatch from `main` only | Requires the explicit `yes` input, the protected `production` environment, pre-deploy backup, and post-deploy health verification. |

Every third-party action is pinned to a full commit SHA. The CI job is limited
to 90 minutes, uses the isolated `ki-ci` Compose project and high loopback
ports, installs Foundry from a SHA-pinned action at a fixed release, and tears
its containers and volumes down when it exits.

## GitHub repository settings

### Current branch ruleset audit — 26 October 2026

The active `Main and develop branch protection` ruleset (ID `18234835`)
targets both `main` and `develop`. It requires a pull request, one approving
review, dismissal of stale approvals after new commits, resolved conversations,
up-to-date branches, linear history, protected deletion, no force pushes, and
the current status checks `CI / ci` and `Security / gitleaks`. The separate
`Version tag protection` ruleset (ID `18234836`) remains active and unchanged.

The ruleset also requires code-owner review, but there is no first-party
`CODEOWNERS` file in `.github/`, the repository root, or `docs/`. Thus the
setting currently has no meaningful first-party ownership map. Two user bypass
actors (`wasabinetwork` and `wasalo`) are configured as `Always allow`; see the
owner decisions below.

GitHub Actions is enabled. Keep the following operating configuration aligned
with the ruleset:

1. Send feature pull requests to `develop`; promote completed release batches
   from `develop` to `main` with a separate pull request. Both branches require
   `CI / ci` and `Security / gitleaks`.
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

#### Ruleset improvements to consider

- Decide whether both `Always allow` bypass entries are needed. Pull-request-
  only bypass prevents direct pushes by those users but still lets them bypass
  rules through a PR; remove bypass entirely if they should not bypass reviews
  or checks. Keep emergency access an explicit repository-owner decision.
- Add `.github/CODEOWNERS` after maintainers assign accountable owners for
  first-party paths. Until then, the code-owner rule does not establish actual
  file ownership.
- **Revisit linear history before the first `develop` → `main` release.** The
  current ruleset applies linear history to both branches, so GitHub requires
  squash or rebase merges. That is fine for feature PRs into `develop`, but a
  long-lived integration branch promoted with rewritten commits can diverge
  from `main` and make later release PRs noisy. For a conventional integration
  branch, consider splitting the rules: keep linear history on `develop`, and
  permit a merge commit for reviewed release PRs into `main` so the release
  preserves ancestry. This requires changing the current ruleset design; it is
  not changed by this documentation/workflow PR.
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
