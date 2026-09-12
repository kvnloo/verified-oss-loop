# HITL — Linear columns are this loop

This kit **is** the HITL contract. CoS and factory workers read **this file**, then [SPEC.md](SPEC.md). Adapter (onboard, origin OSS, traction as an outcome view): [docs/factory.md](docs/factory.md).

Do not invent a third process. Do not mint a parallel factory protocol in another repo. Linear is the factory board. GitHub remains contribution authority.

## Origin-write gate

`github_writes=0` until **Todo**. Triage and Backlog may clone, read, and draft locally. They must not open origin issues, comments, or PRs.

Workers never merge `main` or `dev` (SPEC §6). Channel automerge is maintainer-configured rollout, not a worker merge key.

## Origin publish (Maintainer Review)

Moving a leaf to **Maintainer Review** **auto-opens** the GitHub **parent** PR from the attached **fork** PR. `scripts/publish-origin-from-hitl.py` does that and **never merges**. Origin PRs are ready (not draft).

Wire Linear Automation to this kit repo: `repository_dispatch` with `event_type: hitl-maintainer-review` and `client_payload.linear_issue` (UUID or `TEAM-N` like `PER-1358`). A 5-minute scheduled `--scan-maintainer-review` publishes even if the webhook is missed. Repo secrets: `HITL_GITHUB_TOKEN` and `LINEAR_API_KEY`. Workflow: `.github/workflows/hitl-publish-origin.yml`.

Non-fork plugin repos fail closed. Do not origin-publish marketplace/plugin copies. `--merge` exits 2. `oss-onboard` does not copy this workflow onto children.

## Traction is not priority

The traction formula (`4*merged + …`) is an outcome view. It does not set claim priority and does not authorize merge.

## Column map (Triage → Done)

| Linear | SPEC loop | GitHub |
|---|---|---|
| Triage | §1 research; issues are not claims | no origin write |
| Backlog | §1 claimable item; human-owned priority | `claimable` issue or origin issue URL |
| Todo | §2 human authorized the bounded claim lease | claim comment; `claimed` |
| In Progress | §3 isolated branch/worktree | contributor branch; no shared mutable `main` |
| Ready to Review | §4 evidence receipt on a **fork** draft | draft PR on the fork; `needs-review` |
| Maintainer Review | §5 origin PR live; independent review | **auto-opens** origin PR from attached fork PR; never merges; 5-minute scan + Linear Automation |
| Done | §6 authorized human/maintainer merged; §7 KEEP | exact merge SHA; close roadmap item |
| Canceled | §7 DISCARD with a lesson | `discard`; do not reopen as volume |

`Duplicate` is SPEC §5 `DISCARD_DUPLICATE`. It is not a claim and is not volume.

## Worker rules

- One leaf per contribution. Do not mint into Todo. Do not bulk-move columns.
- Origin-open at mint time → Ready to Review, never Backlog.
- Same-PR CI/review bounce is authorized on In Progress / Ready to Review / Maintainer Review with a live origin URL.
- Origin review bots (Greptile, Codecov, CodSpeed, Prow, hassfest, …) are independent reviewers. They do not authorize merge.
- Opted-in `kvnloo/*`: `./bin/oss-onboard DIR --with-automation`. Origin OSS: follow *their* CONTRIBUTING; do not dump loop labels.
