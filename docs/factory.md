# OSS factory adapter

How [kvnloo/oss-factory](https://github.com/kvnloo/oss-factory) uses **this** protocol to keep quality high on repos that follow the Verified OSS Loop. This is not a second scheduler. Linear remains the factory HITL board. GitHub remains the contribution authority.

## Which repos

| Kind | Apply this kit? | Rule |
|---|---|---|
| `kvnloo/*` that opted into the standard | **Yes** | `./bin/oss-onboard DIR --with-automation --labels` |
| Origin OSS (LiteLLM, rust-lang, HA, …) | **No dump** | Follow *their* CONTRIBUTING, CODEOWNERS, and bots. Map factory HITL onto *their* process |
| Private factory IaC (`oss-factory`) | Contract only | HITL columns below; do not onboard terraform as an app |

"Follow this standard" means the repo already has, or a maintainer asked for, `AGENTS.md` + claim labels + evidence PRs + workers-never-merge.

## HITL columns are the loop

[factory/HITL.md](https://github.com/kvnloo/oss-factory/blob/main/factory/HITL.md) columns map 1:1 onto [SPEC.md](../SPEC.md). Do not invent parallel states.

| Linear (factory) | Loop step | GitHub |
|---|---|---|
| Triage | research; issues are not claims | no origin write |
| Backlog | claimable item, human-owned priority | `claimable` issue or origin issue URL |
| Todo | human authorized the bounded claim | claim comment; `claimed` |
| In Progress | isolated branch/worktree | contributor branch; no shared mutable `main` |
| Ready to Review | evidence receipt on a **fork** draft | draft PR on the fork; `needs-review` |
| Maintainer Review | origin PR live; independent review | origin PR; receipt + CI + review bots |
| Done | authorized human/maintainer merged | exact merge SHA; `keep` / close roadmap item |
| Canceled | DISCARD with a lesson | `discard`; do not reopen as volume |

`github_writes=0` until Todo is the factory's origin-write gate. It is stricter than, and compatible with, workers-never-merge.

## Optimizing a kvnloo repo that follows the standard

One pass, then stop:

```bash
git clone https://github.com/kvnloo/verified-oss-loop
./bin/oss-onboard /path/to/repo --with-automation --labels
bash /path/to/repo/tests/smoke.sh 2>/dev/null || true
```

Then, in that repo:

1. Fill `AGENTS.md` ownership and pin the unit command `detect-stack.sh` already wrote.
2. Protect `main` (PR required, receipt + unit checks, no worker merge).
3. Optionally install **one** AI reviewer (Greptile / CodeRabbit / Bugbot) and coverage/perf apps. Catalog: [quality-bots.md](quality-bots.md).
4. Open a PR with an evidence receipt. **Never merge.**

Do not:

- Copy LiteLLM's entire workflow tree into a spec repo.
- Add npm/pip/cargo Dependabot ecosystems unless that lockfile exists.
- Treat factory traction (`4*merged + …`) as roadmap priority. Score is an outcome view, not a claim lease.
- Spray comments to farm `conversations` weight.

## Origin OSS (read their bots, do not replace them)

When the factory contributes to a community that already has S-tier bots (example: [BerriAI/litellm#40744](https://github.com/BerriAI/litellm/pull/40744)):

1. Search origin issues/PRs. Stop on overlap.
2. Follow origin PR template **and** attach a loop-shaped receipt if it fits in the origin "Screenshots / Proof" section without fighting their template.
3. Treat Greptile/Codecov/CodSpeed as independent review evidence. Fix the objections they raise when they are right.
4. Do not install verified-oss-loop labels onto origin.
5. Do not merge origin. Maintainer Review waits on *their* authorized path.

## Evidence the factory already measures

oss-factory traction rewards maintainer-validated outcomes (merged, salvage, heat) and punishes spray. That is the same idea as SPEC §7 KEEP/DISCARD and issue #1's impact ladder, without shipping a game in this pass.

When recording a factory outcome, bind it to `head_revision` / merge SHA. Tests from another head are not evidence. Bot comments are not maintainer engagement.

## Skills

Factory workers donating a pass on a loop-adopting repo: `skills/autodevelop/SKILL.md` in the **target**. This file is for the factory control plane.
