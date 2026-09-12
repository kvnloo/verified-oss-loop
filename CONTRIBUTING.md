# Contributing

This repo is the Verified OSS Loop: a protocol (`SPEC.md`) plus an onboarding kit (`scripts/`, `templates/`).

1. Search issues and PRs. Do not duplicate.
2. Claim one `claimable` issue. Issues are not claims.
3. Isolated branch. Fill the PR evidence block.
4. Workers never merge `main` or `dev`. Default scheme is `rolling` (`docs/rollout.md`).

Project policy here wins over a worker's house rules. See `REFERENCES.md` for credited sources.

CI checks the evidence YAML and exact head (`scripts/check-receipt.py`). Paste `prompt.md` into any harness to autodevelop. Quality-bot catalog: `docs/quality-bots.md`. Agent graph/LSP/pstack tools: `docs/agent-onboarding.md`. Kit vs local skills: `docs/kit-inventory.md`. Rollout schemes: `docs/rollout.md`. Factory HITL: `HITL.md`. Factory adapter: `docs/factory.md`. Orient before edit (`skills/orient/SKILL.md`); smallest complete change (`skills/anti-slop/SKILL.md`).
