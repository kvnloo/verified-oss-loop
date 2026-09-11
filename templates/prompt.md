# Autodevelop — {{PROJECT}}

Paste **this entire file** as the first message to any coding agent (Cursor, Codex, Claude Code, Hermes, …). Do not summarize it. Work in **this** repository, not a different clone.

| | |
|---|---|
| **This repo** | {{REPO_URL}} |
| Clone | `git clone {{REPO_URL}}.git` |
| Protocol | [Verified OSS Loop](https://github.com/kvnloo/verified-oss-loop) (`SPEC.md` in that kit; this tree has `AGENTS.md`) |

You are a contributor, not a maintainer. Donate **one** coding pass. **Never merge `main`.**

## Do

1. Clone or open {{REPO_URL}}. `cd` into that tree. `git fetch origin`. Branch from `origin/main` unless the issue names another base.
2. Read `AGENTS.md` and `CONTRIBUTING.md` in this repo. Follow them if they conflict with this file.
3. Search open issues and PRs. Stop on overlap.

```bash
gh issue list --repo {{OWNER}}/{{REPO}} --label claimable --state open
gh pr list --repo {{OWNER}}/{{REPO}} --state open
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

5. Orient before edit (`skills/orient/SKILL.md`). If GitNexus MCP is already there: `query` → `context` → `impact`. Do not run `gitnexus analyze` unless a human asked.
6. Fail, then pass (`skills/tdd/SKILL.md`). Unit command: `{{UNIT_CMD}}`. Mutation: `{{MUTATOR_CMD}}` (write `n/a` if that is what the tree says; do not invent a score).
7. Smallest complete change (`skills/anti-slop/SKILL.md`). If pstack is already installed, `/poteto-mode` is allowed; still never merge.
8. Open a PR on {{REPO_URL}} with `.github/PULL_REQUEST_TEMPLATE.md` filled. Bind evidence to `head_revision`. **Do not merge.**

## Stop

- Nothing is `claimable`, a live claim exists, or a competing PR covers the scope.
- You would need secrets, pairing tokens, or maintainer credentials.
- You were about to merge, force-push `main`, overwrite `LICENSE`, or dump GitNexus/pstack into the tree.

If you stop, leave a comment with the blocker. Do not open a consolation PR.

## Skills in this repo

`skills/autodevelop/SKILL.md` is the same loop. `skills/verify/SKILL.md` is the receipt. Do not invent a parallel process.
