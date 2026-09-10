# References

This protocol adapts older OSS community-health work for an AI-native era. Credit first; then the gap.

Expanded table: [docs/prior-art.md](docs/prior-art.md).

## Pre-AI (adapt, do not replace)

| Project | What we take | What we do not take |
|---|---|---|
| [cookiecutter/cookiecutter](https://github.com/cookiecutter/cookiecutter) (BSD-3) | project generation as a *scripted* copy, not a dump of one stack | a Python-only cookie that bakes bun/pytest into every repo |
| [copier-org/copier](https://github.com/copier-org/copier) (MIT) | updateable templates; answers as data | requiring copier to adopt the loop |
| [RichardLitt/standard-readme](https://github.com/RichardLitt/standard-readme) (CC0) | README sections: Why / Install / Use / Contribute | a second spec language |
| [GitHub community health files](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file) | CONTRIBUTING, SECURITY, issue/PR templates, CODEOWNERS | GitHub-only process as the whole loop |
| [todogroup/repolinter](https://github.com/todogroup/repolinter) (Apache-2.0) | lint the *presence* of health files | treating lint as evidence of correctness |
| [ossf/scorecard](https://github.com/ossf/scorecard) (Apache-2.0) | repo security posture as a check, not a merge bot | pay-to-win or token-gated priority |
| [joelparkerhenderson/github-templates](https://github.com/joelparkerhenderson/github-templates) | issue/PR markdown patterns | a 200-file kitchen sink |
| [higress-group/issue-spec](https://github.com/higress-group/issue-spec) | proposal → design → implementation DAG | claiming issues are claims |
| [cdevents/spec](https://github.com/cdevents/spec) (Apache-2.0) | delivery *events*, not contribution contracts | replacing git/GitHub as source of truth |

## Verification tools (stack-detected, not forced)

| Tool | Stack |
|---|---|
| [stryker-mutator/stryker-js](https://github.com/stryker-mutator/stryker-js) | JS/TS |
| [boxed/mutmut](https://github.com/boxed/mutmut) | Python |
| [sourcefrog/cargo-mutants](https://github.com/sourcefrog/cargo-mutants) | Rust |
| `go test` / fuzz | Go (no default mutator; do not invent one) |

## AI-native conventions

| Source | Role |
|---|---|
| [agents.md](https://agents.md/) | `AGENTS.md` as the agent-facing contract |
| [kvnloo/dash](https://github.com/kvnloo/dash) | exemplar: workers never merge, Unattended vs Copilot, mutation score, evidence block |
| [kvnloo/hermes-keel](https://github.com/kvnloo/hermes-keel) | exemplar: Level-0 capability receipts, fail closed |
| [kvnloo/aodl](https://github.com/kvnloo/aodl) | exemplar: schema + fail-closed validator as proof |

## Origin of this loop

Grew from the [Community-wide Distributed Self-Development Loop](https://github.com/AndyMik90/Aperant/discussions/306), then Hermes autoresearch ([#5114](https://github.com/NousResearch/hermes-agent/issues/5114)) and reversible harness refinement ([#93306](https://github.com/NousResearch/hermes-agent/issues/93306)).

## Gap those projects leave

None of the above give you, together:

1. **Claim leases** that expire (issues are not claims)
2. **Workers never merge** as a hard rule, including cloud agents
3. **Revision-bound evidence receipts** (RED/GREEN/sabotage + exact head)
4. **Harness-neutral** TDD/mutation *setup* — detect stack at runtime, do not dump bun scripts into a Python repo
5. **KEEP/DISCARD** learning that feeds the roadmap without a second scheduler

That is this repository.
