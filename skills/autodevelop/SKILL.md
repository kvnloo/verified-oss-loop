# Autodevelop

Donate one coding pass. Do not invent a parallel process.

## Do

1. Read root `AGENTS.md` and `CONTRIBUTING.md`.
2. `git fetch origin`. `python3 .verified-oss-loop/rollout.py show` (or `python3 scripts/rollout.py show`). Branch from `origin/$(python3 .verified-oss-loop/rollout.py get worker_base)` unless the issue names another base. Day-pass PRs target `feature_target`. Overnight PRs target `overnight_target`.
3. Search open issues and PRs. Stop on overlap.
4. Claim **one** `claimable` issue that is not `claimed`. 24h lease unless the project says otherwise.
5. Orient (`skills/orient/SKILL.md`). Graph MCP if present; otherwise search and read. Do not run `gitnexus analyze`.
6. Fail, then pass (`skills/tdd/SKILL.md`).
7. Shrink to the smallest complete change (`skills/anti-slop/SKILL.md`). If pstack is already installed, `/poteto-mode` is allowed; still never merge (`skills/pstack/SKILL.md`). New skills go through `skills/dr-eggbot/SKILL.md`.
8. Run the unit command from `AGENTS.md`. Mutation only if it is not `n/a`.
9. Open a PR at `feature_target` (day) or `overnight_target` (overnight) with the evidence receipt. **Never merge `main` or `dev`.** Independent review bots are not merge. Do not merge preview/nightly yourself.

## Stop

- Nothing is `claimable`.
- A live claim newer than the lease exists.
- A competing PR already covers the scope.
- You would need secrets, pairing tokens, or maintainer credentials.
- Mutation is `n/a` and you were about to write a score anyway.

If you stop, leave a comment with the blocker. Do not open a consolation PR.
