# Quality bots for S-tier OSS

This is **not a second loop**. [SPEC.md](../SPEC.md) remains the contribution contract. Bots here are Level-1 assistants: they check, label, review, and record evidence. Workers never merge `main` or `dev`. They do not redefine the roadmap. Kubernetes Tide is maintainer-configured merge automation, not a worker. Preview/nightly automerge is channel policy from [rollout.md](rollout.md).

`--with-automation` copies stack-neutral checks. Account-backed apps (Greptile, Codecov, CodSpeed, CodeRabbit) stay a catalog: install them in GitHub settings if the project wants them. `oss-onboard` must not bake bun, pytest, cargo, or a vendor GitHub App into every target.

## Layers (what S-tier repos actually run)

| Layer | Job in this protocol | Examples | Copied by this kit? |
|---|---|---|---|
| 1. Contribution contract | claim lease, labels, evidence PR, workers never merge `main`/`dev` | this repo | yes |
| 2. Hygiene | stale claims/PRs, path labels | [actions/stale](https://github.com/actions/stale), [actions/labeler](https://github.com/actions/labeler) | `--with-automation` |
| 3. Receipt / exact head | Level 1: receipt completeness, SHA bind, claim expiry | CPython [bedevere](https://github.com/python/bedevere); `scripts/check-receipt.py`, `scripts/expire-claims.sh` | `--with-automation` |
| 4. Independent review | generation ≠ verification | Greptile, CodeRabbit, Cursor Bugbot, Copilot code review, rust-lang [triagebot](https://github.com/rust-lang/triagebot) | catalog only |
| 5. Correctness evidence | unit, mutation, schema, lint | project CI; LiteLLM `mutation-test.yml` + mutmut; Home Assistant hassfest | stack-detected, not dumped |
| 6. Coverage / perf evidence | coverage and regression numbers bound to the head | [Codecov](https://about.codecov.io/), [CodSpeed](https://codspeed.io/) | catalog only |
| 7. Security health | Scorecard, SAST, deps, Actions hardening | [OpenSSF Scorecard](https://github.com/ossf/scorecard), CodeQL, Semgrep, OSV, [zizmor](https://github.com/zizmorcore/zizmor), Dependabot | Scorecard + Actions Dependabot on `--with-automation` |
| 8. Merge authority | CODEOWNERS, branch protection, merge queue, channel automerge | Kubernetes [OWNERS](https://github.com/kubernetes/community/blob/main/contributors/guide/owners.md) + Tide; GitHub merge queue; Arch-style rolling | CODEOWNERS file; humans still merge `main`/`dev`; preview/nightly automerge only if `rollout.yml` allows |

## Repositories worth copying *practices* from (not their apps)

Live example that motivated this pass: [BerriAI/litellm#40744](https://github.com/BerriAI/litellm/pull/40744). One model-price PR was independently scored by **Greptile** (confidence 4/5, with a test-quality objection), **CodSpeed** (no perf change), and **Codecov** (modified lines covered). Maintainers still own merge. LiteLLM's workflow tree also runs Scorecard, CodeQL, Semgrep, OSV, mutation tests, duplicate close, LLM issue triage, and `guard-main-branch` — a dense bot mesh around a human merge gate.

| Repo | Bot mesh | Take | Skip |
|---|---|---|---|
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | Greptile, CodSpeed, Codecov, Scorecard, CodeQL, Semgrep, mutmut, duplicate/stale, LLM triage | Independent review + evidence bots on every PR; Greptile is a *reviewer*, not a merger | Greptile 4/5 as a hard merge rule without a human; LLM auto-triage that opens issues |
| [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) | Prow, Tide, Blunderbuss, OWNERS `/lgtm` `/approve` | Path owners; labels are merge *criteria*; bots assign reviewers | Tide auto-merge is maintainer policy. Workers in this protocol never get that role |
| [rust-lang/rust](https://github.com/rust-lang/rust) + [triagebot](https://github.com/rust-lang/triagebot) | rustbot, triagebot, rfcbot, bors-shaped queues | `/claim`-style commands, nominate, labels, backport | Homu/bors as a worker merge key |
| [python/cpython](https://github.com/python/cpython) | [bedevere](https://github.com/python/bedevere), [miss-islington](https://github.com/python/miss-islington), [the-knights-who-say-ni](https://github.com/python/the-knights-who-say-ni) | Receipt completeness (NEWS, issue #, CLA) before review time is spent | Auto-merge backports unless the project already has that maintainer path |
| [home-assistant/core](https://github.com/home-assistant/core) | hassfest, CODEOWNERS pings, Codecov, Dependabot **and** Renovate, Copilot instructions | Integration-shaped CI; bots ping owners; humans merge | Dual Dependabot+Renovate noise; `copilot-instructions.md` as a second AGENTS.md |
| [ossf/scorecard](https://github.com/ossf/scorecard) | its own Action | Branch protection, token permissions, pinned Actions, security policy | Treating Scorecard 10/10 as proof the code is correct |

## AI review bots (independent reviewer, never merge)

These are the 2026 independent-review layer. Pick **one** primary; a second bug-focused bot is optional. Do not stack four commenters.

| Bot | Strength | Protocol role |
|---|---|---|
| [Greptile](https://www.greptile.com/) | Full-repo index; confidence score; cites call sites | Independent review. LiteLLM asks for ≥4/5 *before requesting maintainer review* — still not merge |
| [CodeRabbit](https://coderabbit.ai/) | Broad PR summary + inline; OSS free tier | Same. Tune noise; do not require it to approve |
| [Cursor Bugbot](https://cursor.com/) | Fewer, bug-shaped findings | Same. Good when the team already lives in Cursor |
| GitHub Copilot code review | Lowest friction if already licensed | Diff-scoped; not a substitute for tests |
| [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent) | Self-hosted review comments | Same, if the project refuses a SaaS app |

**Rules for this protocol**

1. An AI review comment is not `APPROVE_EXACT_HEAD`.
2. A confidence score is evidence for the human reviewer, not a merge bit.
3. The implementer does not self-approve, including via a bot they control.
4. Required status checks may include receipt, unit CI, Scorecard, and CodeQL. They must not include "the coding agent liked it".

## What `--with-automation` installs

Copied into the target (still no merge of `main`/`dev`):

- `.github/workflows/stale.yml` — quiet issues/PRs; exempt `claimed`
- `.github/workflows/labeler.yml` + `labeler.yml`
- `.github/workflows/receipt.yml` — evidence YAML + exact head
- `.github/workflows/claim-expiry.yml` — expired leases return to `claimable`
- `.github/workflows/scorecard.yml` — OpenSSF Scorecard SARIF
- `.github/dependabot.yml` — **github-actions only**
- `.github/CODEOWNERS`
- `.github/scripts/check-receipt.py` and `expire-claims.sh`
- `.github/scripts/create-labels.sh`
- `.github/workflows/automerge-preview.yml` / `automerge-nightly.yml` / `promote-preview.yml` — gated by `.verified-oss-loop/rollout.yml` ([rollout.md](rollout.md))
- `scripts/rollout.py` and `scripts/ensure-rollout-branches.sh`

Not copied (need accounts, secrets, or a language lockfile):

- Greptile / CodeRabbit / Bugbot / Copilot
- Codecov / CodSpeed
- CodeQL / Semgrep / OSV / zizmor (add when the project has a security owner)
- Renovate, release-please, changesets, semantic-release
- Language Dependabot ecosystems

## Maintainer settings (not files)

Bots only help if GitHub settings match the contract:

1. Protect `main` and `dev`: no force-push, no deletions, require a PR, require the smoke/receipt checks, dismiss stale approvals. Leave `preview` and `nightly` loose under `rolling`/`staged`.
2. CODEOWNERS review is optional for tiny specs; required for apps.
3. Merge queue is optional. If enabled, CI must listen for `merge_group`. Queue merge is still the **authorized path**, not a worker.
4. Do not grant `GITHUB_TOKEN` write to contents on pull_request from forks.
5. Project `SECURITY.md` and private vulnerability reporting override public issue workflows.

## Factory

Repos the OSS factory maintains that opt into this standard get the same kit via `./bin/oss-onboard DIR --with-automation`. Origin communities keep their own bots. See [factory.md](factory.md). How Linux/k8s/rustc kept quality at volume: [quality-at-scale.md](quality-at-scale.md). Graph/LSP orientation tools are a separate catalog: [agent-onboarding.md](agent-onboarding.md).
