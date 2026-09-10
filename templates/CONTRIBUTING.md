# Contributing

Humans and coding agents work on this repository together. This file is how to **use** the project and how to **contribute**. Project policy in `AGENTS.md` and `SECURITY.md` wins if anything conflicts.

## Use

See the README for install, run, and configuration. Do not commit secrets.

## Contribute

### Autodevelop (agents)

If you were told to autodevelop, donate a coding pass, or pick the next issue: read `AGENTS.md` and `skills/autodevelop/SKILL.md`. Do not invent a parallel process.

Workers:

1. Claim one `claimable` issue (24h lease).
2. Work on a branch from `origin/main`.
3. Fail, then pass.
4. Open a PR with an evidence receipt.
5. **Never merge `main`.**

### Humans

Same loop, without the claim bot if you are a maintainer. You still do not need a second process.

## Evidence

Every PR fills `.github/PULL_REQUEST_TEMPLATE.md`:

- issue number
- base SHA and head SHA
- red command (failing repro) and green command
- mutation command and score, or `n/a`
- contribution mode: unattended (cloud agent) or copilot (human-supervised)

Tests from another head are not evidence.

## Prior art

Contribution contract: [kvnloo/verified-oss-loop](https://github.com/kvnloo/verified-oss-loop). Agent file convention: [agents.md](https://agents.md/).
