# Notes for agents

This repository is the protocol and the onboarding kit. It is not an application.

- `SPEC.md` is the contribution contract. Do not invent a second loop.
- `scripts/` and `bin/oss-onboard` copy templates and detect stack. Do not bake bun, pytest, or cargo into every target.
- Unit proof for this kit: `bash tests/smoke.sh`. Mutation is `n/a`.
- Workers never merge `main`.
- Do not force-push `main`.
- Credit sources in `REFERENCES.md` and `docs/prior-art.md`. Do not drop pre-AI OSS templates when adding AI-native files.
- Quality bots are Level 1 assistants (`docs/quality-bots.md`). They review and check receipts. They do not merge.
- Factory workers: `docs/factory.md` and `skills/factory/SKILL.md`. Onboard opted-in `kvnloo/*` repos; do not dump the loop onto origin OSS.

If you are donating a pass: pick one issue, claim it, open a PR with an evidence receipt, stop.
