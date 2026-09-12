# OSS factory adapter

How Linear factory HITL uses **this** Verified OSS Loop protocol. Canonical column contract: [HITL.md](../HITL.md). CoS keeps that file in this kit so workers cannot invent a third process. This is not a second scheduler. Linear remains the factory board. GitHub remains the contribution authority.

## Which repos

| Kind | Apply this kit? | Rule |
|---|---|---|
| `kvnloo/*` that opted into the standard | **Yes** | `./bin/oss-onboard DIR --with-automation --labels` (default `--scheme rolling`). Mature trees: `--layout mature`. |
| Origin OSS (LiteLLM, rust-lang, HA, …) | **No dump** | Follow *their* CONTRIBUTING, CODEOWNERS, and bots. Map factory HITL onto *their* process |
| Factory control plane / IaC | Contract only | [HITL.md](../HITL.md); do not onboard terraform as an app. Do not mint a parallel factory protocol. |

"Follow this standard" means the repo already has, or a maintainer asked for, `AGENTS.md` + claim labels + evidence PRs + workers-never-merge.

## HITL columns are the loop

The map lives in [HITL.md](../HITL.md) (Triage → … → Done onto [SPEC.md](../SPEC.md)). Do not invent parallel states. `github_writes=0` until Todo is the origin-write gate. It is stricter than, and compatible with, workers-never-merge.

## Optimizing a kvnloo repo that follows the standard

One pass, then stop:

```bash
git clone https://github.com/kvnloo/verified-oss-loop
./bin/oss-onboard /path/to/repo --with-automation --labels
bash /path/to/repo/tests/smoke.sh 2>/dev/null || true
```

Then, in that repo:

1. Fill `AGENTS.md` ownership and pin the unit command `detect-stack.sh` already wrote.
2. Protect `main` and `dev` (PR required, receipt + unit checks, no worker merge). `preview`/`nightly` stay loose under the default `rolling` scheme. [rollout.md](rollout.md).
3. Optionally install **one** AI reviewer (Greptile / CodeRabbit / Bugbot) and coverage/perf apps. Catalog: [quality-bots.md](quality-bots.md).
4. Re-run `oss-onboard` after a kit release. Inventory (`.verified-oss-loop/inventory.yml`) updates kit skills and leaves local pstack/eggbot copies alone. See [kit-inventory.md](kit-inventory.md). Paste that repo's `prompt.md` into any harness (it links to itself).
5. Orient (`skills/orient/SKILL.md`) then TDD, then shrink (`skills/anti-slop/SKILL.md`). Do not run `gitnexus analyze` unless the maintainer already uses GitNexus.
6. Open a PR with an evidence receipt. **Never merge `main` or `dev`.**

Do not:

- Copy LiteLLM's entire workflow tree into a spec repo.
- Add npm/pip/cargo Dependabot ecosystems unless that lockfile exists.
- Treat factory traction (`4*merged + …`) as roadmap or claim priority. Score is an outcome view, not a claim lease. The traction formula does not set claim priority.
- Spray comments to farm `conversations` weight.
- Run `gitnexus analyze` from `oss-onboard` or an unattended claim. Graph tools are catalog-only until a human installed them.

## Origin OSS (read their bots, do not replace them)

When the factory contributes to a community that already has S-tier bots (example: [BerriAI/litellm#40744](https://github.com/BerriAI/litellm/pull/40744)):

1. Search origin issues/PRs. Stop on overlap.
2. Follow origin PR template **and** attach a loop-shaped receipt if it fits in the origin "Screenshots / Proof" section without fighting their template.
3. Treat Greptile/Codecov/CodSpeed as independent review evidence. Fix the objections they raise when they are right.
4. Do not install verified-oss-loop labels onto origin.
5. Do not merge origin. Maintainer Review waits on *their* authorized path.

## Origin publish from Maintainer Review

This kit repo (not origin, not plugin copies) owns the publisher:

```bash
python3 scripts/publish-origin-from-hitl.py --self-test
python3 scripts/publish-origin-from-hitl.py --merge   # exit 2 — never merges
```

Moving Linear to **Maintainer Review** opens the GitHub **parent** PR from the attached **fork** PR. Workflow: `.github/workflows/hitl-publish-origin.yml` on `repository_dispatch` `event_type: hitl-maintainer-review`. Secrets: `HITL_GITHUB_TOKEN`, `LINEAR_API_KEY`. Non-fork plugin repos fail closed. `oss-onboard --with-automation` must not dump this workflow into children.

## Evidence the factory already measures

Factory traction rewards maintainer-validated outcomes (merged, salvage, heat) and punishes spray. That is the same idea as SPEC §7 KEEP/DISCARD and issue #1's impact ladder, without shipping a game in this pass. The traction formula does not set claim priority.

When recording a factory outcome, bind it to `head_revision` / merge SHA. Tests from another head are not evidence. Bot comments are not maintainer engagement.

## Skills

Factory workers donating a pass on a loop-adopting repo: `skills/autodevelop/SKILL.md` in the **target** (orient → TDD → anti-slop). Graph/LSP catalog: [agent-onboarding.md](agent-onboarding.md). Quality at volume (Linux/k8s TAKE/SKIP): [quality-at-scale.md](quality-at-scale.md). This file is for the factory control plane.
