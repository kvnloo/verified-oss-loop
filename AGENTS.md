# Notes for agents

This repository is the protocol and the onboarding kit. It is not an application.

- `SPEC.md` is the contribution contract. Do not invent a second loop.
- `scripts/` and `bin/oss-onboard` copy templates and detect stack. Do not bake bun, pytest, or cargo into every target.
- Unit proof for this kit: `bash tests/smoke.sh`. Mutation is `n/a`.
- Workers never merge `main` or `dev`. Default rollout is Arch-style `rolling` (`docs/rollout.md`, `.verified-oss-loop/rollout.yml`). Branch from `origin/$(python3 scripts/rollout.py get worker_base)`. Day-pass PRs target `feature_target`; overnight PRs target `overnight_target`. Do not merge preview/nightly yourself.
- Do not force-push `main`.
- Credit sources in `REFERENCES.md` and `docs/prior-art.md`. Do not drop pre-AI OSS templates when adding AI-native files.
- Quality bots are Level 1 assistants (`docs/quality-bots.md`). They review and check receipts. They do not merge `main` or `dev`.
- Factory workers: `docs/factory.md` and `skills/factory/SKILL.md`. Onboard opted-in `kvnloo/*` repos; do not dump the loop onto origin OSS.
- Orient before edit (`skills/orient/SKILL.md`). GitNexus/Serena if already present; never `gitnexus analyze` from onboard. Catalog: `docs/agent-onboarding.md`.
- Smallest complete change (`skills/anti-slop/SKILL.md`). Do not duplicate `AGENTS.md` into `CLAUDE.md`.
- pstack / Dr eggbot: `skills/pstack/SKILL.md`, `skills/dr-eggbot/SKILL.md`. Use the Cursor plugin or Grok bot if already installed; do not dump those trees. Workers never merge `main`/`dev` even if a pstack playbook lands PRs.
- Kit vs local skills: `.verified-oss-loop/inventory.yml`. Re-run `oss-onboard` to pick up new kit skills. Never overwrite `source: local`.
- Paste `prompt.md` into any harness to autodevelop this kit. Onboarded repos get a `prompt.md` that links to themselves.

If you are donating a pass: paste `prompt.md` into any harness (it links to this repo), pick one issue, claim it, open a PR with an evidence receipt, stop.
