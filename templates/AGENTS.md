# Notes for agents — {{PROJECT}}

You are a contributor, not a maintainer. Workers open PRs. They never merge `main`.

This project follows the [Verified OSS Loop](https://github.com/kvnloo/verified-oss-loop). Issues are not claims. AI work is untrusted until proven.

## First 60 seconds

1. Read this file, then `CONTRIBUTING.md`.
2. `git fetch origin` and branch from `origin/main` unless the issue names another base.
3. Search open issues and PRs. Do not duplicate in-flight work.

```bash
gh issue list --label claimable --state open
gh pr list --state open
```

## Pick and claim

Take **one** open issue labeled `claimable` and not `claimed`. Prefer `priority:P0`, then `P1`, then `good-first-issue`. Skip `needs-discussion` unless a human assigned it.

If nothing is claimable: stop. Comment a one-paragraph proposal on the newest `needs-discussion` issue. Do not start coding.

Claim comment (24h lease unless the project says otherwise):

```text
claiming for autodevelop
claimant: <github login or agent id>
base: <git rev-parse origin/main>
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
3. Run unit tests on the touched surface.
4. If mutation is not `n/a`, run it on the contract you changed. A surviving mutant is a missing assertion.
5. Open a PR. Fill `.github/PULL_REQUEST_TEMPLATE.md`. Never merge.

## Do not

- Commit secrets, tokens, `.env`, or pairing files.
- Merge `main`.
- Redefine the roadmap.
- Claim mutation coverage that the stack cannot run.
- Overwrite `LICENSE`.
