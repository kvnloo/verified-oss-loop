# Contributing

This repo is the Verified OSS Loop: a protocol (`SPEC.md`) plus an onboarding kit (`scripts/`, `templates/`). Project policy here wins over a worker's house rules.

## How an issue becomes a PR

Community speed comes from a **thin queue**, not from more unlabeled tickets.

1. **Search** issues and PRs. Cluster near-duplicates instead of filing a twin (`scripts/cluster-similar-issues.py` is the offline helper; do not scrape live trackers from CI).
2. **Discuss.** File a Proposal, Bug, or Feature form. Those labels include `needs-discussion`. Overnight workers may add a one-paragraph proposal on the newest discussion issue. They must not self-apply `claimable`.
3. **Maintainers promote** one leaf to `claimable` (and usually `priority:P0`–`P3` or `good-first-issue`). Linear Todo is the same gate in the factory (`HITL.md`).
4. **Claim** that one issue. Issues are not claims. Lease YAML on the issue, then an isolated branch.
5. **One PR, one `head_revision`.** Fill the evidence block **before** `git push` when you can. Receipt CI fetches the **live** PR body so a later edit still matches the SHA. Workers never merge `main` or `dev`.

Unlabeled issues sit forever: they are neither discussion nor work. Prefer the forms.

## Donate a pass

Paste `prompt.md` into any harness (Hermes, Cursor, `omp` / oh-my-pi, …). Follow Work / Triage / Stop in that file. Do not invent a second loop. Isolated proof for this kit: `bash tests/smoke.sh`. CI hygiene: `docs/ci-cd.md`.

Default rollout scheme is `rolling` (`docs/rollout.md`).

Quality-bot catalog: `docs/quality-bots.md`. Agent graph/LSP/pstack: `docs/agent-onboarding.md`. Kit vs local skills: `docs/kit-inventory.md`. Factory HITL: `HITL.md`. Adapter: `docs/factory.md`. Orient (`skills/orient/SKILL.md`); smallest complete change (`skills/anti-slop/SKILL.md`). Credit: `REFERENCES.md`.
