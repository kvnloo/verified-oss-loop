# Autodevelop — verified-oss-loop

Paste **this entire file** as the first message to any coding agent (Cursor, Codex, Claude Code, Hermes, …). Do not summarize it. Work in **this** repository, not a different clone.

| | |
|---|---|
| **This repo** | https://github.com/kvnloo/verified-oss-loop |
| Clone | `git clone https://github.com/kvnloo/verified-oss-loop.git` |
| Protocol | This tree *is* the kit. Contract: `SPEC.md`. Do not invent a second loop. |

You are a contributor, not a maintainer. Donate **one** coding pass. **Never merge `main`.**

## Do

1. Clone or open https://github.com/kvnloo/verified-oss-loop. `cd` into that tree. `git fetch origin`. Branch from `origin/main` unless the issue names another base.
2. Read `AGENTS.md` and `CONTRIBUTING.md`. Follow them if they conflict with this file.
3. Search open issues and PRs. Stop on overlap.

```bash
gh issue list --repo kvnloo/verified-oss-loop --label claimable --state open
gh pr list --repo kvnloo/verified-oss-loop --state open
```

4. Claim **one** `claimable` issue that is not `claimed`. Prefer `priority:P0`, then `P1`, then `good-first-issue`. Skip `needs-discussion` unless a human assigned it. If nothing is claimable: stop. Comment a one-paragraph proposal on the newest `needs-discussion` issue. Do not start coding.

Claim comment (24h lease unless the project says otherwise):

```text
claiming for autodevelop
claimant: <github login or agent id>
base: <git rev-parse origin/main>
expires: <now + 24h UTC>
scope: <one sentence>
```

Then add `claimed` and remove `claimable`.

5. Orient before edit (`skills/orient/SKILL.md`). This kit is templates and shell, not an application. Do not run `gitnexus analyze`. Do not dump pstack or Dr Eggbot into the tree.
6. Fail, then pass (`skills/tdd/SKILL.md`). Unit command: `bash tests/smoke.sh`. Mutation: `n/a`.
7. Smallest complete change (`skills/anti-slop/SKILL.md`). Re-runs of `oss-onboard` must not overwrite `source: local` skills (`.verified-oss-loop/inventory.yml`).
8. Open a PR on https://github.com/kvnloo/verified-oss-loop with `.github/PULL_REQUEST_TEMPLATE.md` filled. Bind evidence to `head_revision`. **Do not merge.**

## Stop

- Nothing is `claimable`, a live claim exists, or a competing PR covers the scope.
- You would need secrets, pairing tokens, or maintainer credentials.
- You were about to merge, force-push `main`, overwrite `LICENSE`, or vendor GitNexus/pstack.

If you stop, leave a comment with the blocker. Do not open a consolation PR.

## Skills in this repo

`skills/autodevelop/SKILL.md` is the same loop. `skills/factory/SKILL.md` is kit-only (not copied to targets). Downstream repos get their own `prompt.md` that links to *themselves*.
