# Verified OSS Loop Specification v0.1

## 1. Roadmap contract

The project publishes a human-owned priority projection:

```yaml
roadmap_revision: sha256-or-git-sha
updated_at: RFC3339
owners: [maintainer-login]
items:
  - issue: 123
    priority: P1
    acceptance: docs-or-test-reference
    claimable: true
```

The roadmap is a projection. Repository history and the project issue/PR tracker remain authoritative.

## 2. Claim lease

A claim is bounded and renewable:

```yaml
issue: 123
claimant: github-login-or-agent-install-id
base_revision: git-sha
claimed_at: RFC3339
expires_at: RFC3339
scope: one-sentence-boundary
work_url: optional-draft-pr-or-branch
```

Before granting a claim, check open/closed PRs, recent commits, roadmap/design decisions, and project policy. Expired claims return to the queue automatically or by maintainer action.

## 3. Execution isolation

Work happens on a contributor-owned branch, fork, container, or worktree. Concurrent workers do not share mutable source state. Secrets and maintainer credentials are never copied to workers. Orient on the existing tree (graph MCP if already present, otherwise search and read) before editing. Do not treat a generated wiki as evidence.

## 4. Evidence receipt

Every proposed change includes:

```yaml
issue: 123
base_revision: git-sha
head_revision: git-sha
changed_files: []
policy_revision: git-sha-or-url
tests:
  red: command + expected failure
  green: command + result
  sabotage: command + expected failure
builds: []
runtime_evidence: []
security_checks: []
resource_usage:
  wall_seconds: optional
  tokens: optional
  api_cost_estimate: optional
limitations: []
ai_assistance: project-required-disclosure
```

Receipts must distinguish local evidence, CI, simulation, and real-device/runtime evidence.

## 5. Review contract

An independent reviewer checks the exact head:

- issue and current thread
- duplicate/overlap state
- project policy
- root cause or feature intent
- sibling surfaces
- evidence receipt reproduction
- security/compatibility/migration risk
- final head stability

Verdicts:

- `APPROVE_EXACT_HEAD`
- `CHANGES_REQUIRED`
- `DISCARD_DUPLICATE`
- `DISCARD_WRONG_DIRECTION`
- `BLOCKED_EXTERNAL`

## 6. Merge authority

Automation may prepare, test, review, label, and recommend. It must not merge `main` or `dev` without the repository's normal authorized human/maintainer path.

Channel automerge (into `preview`, and into `nightly` when `scheme: rolling`) is allowed only when `.verified-oss-loop/rollout.yml` authorizes that channel, and only for same-repo PRs. That is maintainer-configured channel policy, not worker merge of production. See [docs/rollout.md](docs/rollout.md). Default scheme is Arch-style `rolling`.

A merged result records the exact merge revision and closes or updates the roadmap item.

## 7. Learning loop

After terminal outcome, record:

```yaml
hypothesis: why the change should help
result: KEEP | DISCARD | PARTIAL
observed_evidence: []
regressions: []
reusable_lesson: optional
roadmap_effect: promote | demote | split | close | none
```

Do not turn one successful contribution into a global rule. Durable lessons follow project governance and privacy policy.

## 8. Security and abuse controls

- Project security policy overrides public issue workflows.
- No automated public vulnerability disclosure.
- No credential transfer to workers.
- No priority based on compute spend, token holdings, or payment.
- Rate-limit issue/PR creation.
- One canonical issue per problem.
- Stop when a competing PR or maintainer branch covers the scope.
- AI disclosure follows repository policy.

## 9. Adoption levels

### Level 0: Manual

Labels, claim comment, PR evidence template, human review. If this kit onboarded the repo, workers follow `skills/orient` then `skills/tdd` then `skills/anti-slop`.

### Level 1: Assisted

Bots check expiry, duplicates, receipt completeness, and exact head. They do not merge `main` or `dev`. Preview/nightly automerge is channel policy from `rollout.yml`, not a worker merge key.

This kit's `--with-automation` copies that layer as stack-neutral workflows (claim expiry, receipt + exact-head check, stale/labeler, OpenSSF Scorecard, Actions Dependabot, CODEOWNERS, plus preview/nightly automerge and promote-preview gated by `rollout.yml`). Catalog of review/coverage/perf apps that need accounts: [docs/quality-bots.md](docs/quality-bots.md). Project policy still wins; do not dump Greptile, Codecov, or a language lockfile updater into every target. Re-running onboard syncs kit-owned files recorded in `.verified-oss-loop/inventory.yml` and does not overwrite `source: local` skills. Default `--scheme rolling`; pass `--scheme staged` or `--scheme stable` for slower repos.

S-tier OSS (Kubernetes Prow/Tide, rust-lang triagebot, CPython bedevere, Home Assistant hassfest, LiteLLM Greptile+CodSpeed+Codecov) uses many specialized bots around a human or explicitly authorized merge path. Independent review bots are SPEC §5 reviewers. They are not SPEC §6 merge authority.

### Level 2: Distributed

Multiple isolated workers claim independent items; a coordinator projects status.

### Level 3: Evaluated self-development

Frozen evaluators produce KEEP/DISCARD receipts and propose roadmap updates. Maintainers retain approval and merge authority.
