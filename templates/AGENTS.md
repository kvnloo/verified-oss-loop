# Notes for agents — {{PROJECT}}

You are a contributor, not a maintainer. Workers open PRs. They never merge `main` or `dev`.

This project follows the [Verified OSS Loop](https://github.com/kvnloo/verified-oss-loop). Issues are not claims. AI work is untrusted until proven.

## First 60 seconds

1. Read this file, then `CONTRIBUTING.md`.
2. `git fetch origin`. `python3 .verified-oss-loop/rollout.py show`. Branch from `origin/$(python3 .verified-oss-loop/rollout.py get worker_base)` unless the issue names another base. Day-pass PRs target `feature_target`. Overnight unattended PRs target `overnight_target`. See `docs/rollout.md` in the kit (or `.verified-oss-loop/rollout.yml` here).
3. Search open issues and PRs. Do not duplicate in-flight work.
4. Orient (`skills/orient/SKILL.md`). If GitNexus MCP is already there: `query` → `context` → `impact`. Do not run `gitnexus analyze` unless a human asked. Else Serena symbols, else `rg` + read. Loop: `skills/autodevelop/SKILL.md`. Receipt: `skills/verify/SKILL.md`. TDD: `skills/tdd/SKILL.md`.

```bash
gh issue list --label claimable --state open
gh pr list --state open
```

## Pick and claim

Take **one** open issue labeled `claimable` and not `claimed`. Prefer `priority:P0`, then `P1`, then `good-first-issue`. Skip `needs-discussion` unless a human assigned it.

If nothing is `claimable`: do not code. **Triage** — if a `needs-discussion` issue exists: one-paragraph proposal on the newest; stop. If none: mint **exactly one** issue from the first untracked item in `ROADMAP.md`, else a failing unit command from `AGENTS.md`, else docs drift; label **`needs-discussion` only**; stop. Do not self-apply `claimable`. Do not rewrite `ROADMAP.md`. **Stop** if triage found nothing untracked, a live claim exists, a competing PR covers the scope, or secrets are required. Comment the blocker only if an issue thread exists. Do not open a consolation PR.

Claim comment (24h lease unless the project says otherwise):

```text
claiming for autodevelop
claimant: <github login or agent id>
base: <git rev-parse origin/$(python3 .verified-oss-loop/rollout.py get worker_base)>
expires: <now + 24h UTC>
scope: <one sentence>
```

Then add `claimed` and remove `claimable`. If a claim newer than 24h exists, pick a different issue.

## Proof

Commands were filled by `init-oss-repo.sh` / `oss-onboard` from the tree it saw. Do not invent a mutation score if mutation is `n/a`.

| Layer | Command |
|---|---|
| Unit | `{{UNIT_CMD}}` |
| Mutation | `{{MUTATOR_CMD}}` |
| Runtime | `{{RUNTIME_CMD}}` |

1. Name the intended vs current behavior.
2. Fail, then pass (see `skills/tdd/SKILL.md`).
3. Keep the smallest complete change (`skills/anti-slop/SKILL.md`).
4. Run unit tests on the touched surface.
5. If mutation is not `n/a`, run it on the contract you changed. A surviving mutant is a missing assertion.
6. Open a PR at `feature_target` (or `overnight_target` if unattended overnight). Fill `.github/PULL_REQUEST_TEMPLATE.md`. Never merge `main` or `dev`. Do not merge preview/nightly yourself; automerge may, when `rollout.yml` allows.
7. If the project runs an independent review bot (Greptile, CodeRabbit, Bugbot, Copilot, …), treat its comments as review, not merge. Fix real findings. Do not wait for a bot to approve itself.

Live site is `main`; nightly is `{base}nightly/` not `{base}preview/nightly/`. Git `preview` ≠ `/preview/`. See `docs/rollout.md` in the kit (`pages-url-map.py`).

## Do not

- Commit secrets, tokens, `.env`, or pairing files.
- Merge `main` or `dev`.
- Redefine the roadmap.
- Claim mutation coverage that the stack cannot run.
- Overwrite `LICENSE`.
- Duplicate `AGENTS.md` into `CLAUDE.md` / `GEMINI.md` / copilot-instructions.
- Run `gitnexus analyze` as a side effect of a claim.
- Dump the pstack plugin or Dr Eggbot marketplace pack into this tree. Pointers: `skills/pstack/SKILL.md`, `skills/dr-eggbot/SKILL.md`.
