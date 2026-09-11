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

## Quality bots (Level 1 assistants, not merge)

| Source | What we take | What we do not take |
|---|---|---|
| [BerriAI/litellm](https://github.com/BerriAI/litellm) ([#40744](https://github.com/BerriAI/litellm/pull/40744)) | Greptile + CodSpeed + Codecov as independent evidence on one PR; Scorecard/CodeQL/Semgrep/mutation as required checks | copying their full workflow tree; Greptile score as merge |
| [kubernetes Prow/Tide](https://docs.prow.k8s.io/docs/components/core/tide/) + [OWNERS](https://github.com/kubernetes/community/blob/main/contributors/guide/owners.md) | path owners, `/lgtm` as review, bots assign reviewers | Tide auto-merge for workers |
| [rust-lang/triagebot](https://github.com/rust-lang/triagebot) | claim/label/nominate commands | homu/bors worker merge keys |
| [python/bedevere](https://github.com/python/bedevere) | receipt completeness before human review time | auto-merge |
| [Arch Linux rolling release](https://wiki.archlinux.org/title/Arch_Linux) | bleeding-edge default: keep `nightly` close to HEAD; promote when preview looks right | treating rolling as a worker merge of `main` |
| [home-assistant/core](https://github.com/home-assistant/core) | hassfest-shaped CI, CODEOWNERS pings | dual Dependabot+Renovate by default; a second AGENTS.md |
| [ossf/scorecard](https://github.com/ossf/scorecard) | branch-protection and token-permission health | Scorecard as a correctness proof |
| Greptile / CodeRabbit / Cursor Bugbot / Copilot review | one independent AI reviewer | stacking four commenters; bot self-approve |

Catalog and factory mapping: [docs/quality-bots.md](docs/quality-bots.md), [docs/factory.md](docs/factory.md).

## Agentic onboarding (catalog, do not vendor)

| Source | What we take | What we do not take |
|---|---|---|
| [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) | If MCP is already present: `query` → `context` → `impact` before edit | Running `gitnexus analyze` from onboard; copying source/skills (PolyForm Noncommercial ≠ Apache-2.0); a second `AGENTS.md` H1 |
| [oraios/serena](https://github.com/oraios/serena) (MIT) | LSP symbol retrieve as the OSS fallback | Dumping Serena into every target |
| [upstash/context7](https://github.com/upstash/context7) (MIT) | Versioned library docs | Using it as a repo graph |
| DeepWiki | Optional orientation wiki | Wiki text as evidence |
| [yamadashy/repomix](https://github.com/yamadashy/repomix) / [cyclotruc/gitingest](https://github.com/cyclotruc/gitingest) | One-shot packed tree | Pasting a whole pack every turn |
| [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep) (MIT) | Structural search when the graph is missing | Replacing tests with search |
| [agents.md](https://agents.md/) | One portable agent file | N copies (`CLAUDE.md` + `GEMINI.md` + copilot-instructions) |
| [pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT, Lauren Tan) | `/poteto-mode` when the plugin is already in the workspace | Dumping the plugin tree; shipping playbooks that merge |
| Dr Eggbot | One-job skill/bot design; fleet healthcheck | Copying the Grok marketplace bot; treating oss-factory as the source (it is not) |

Skills: [docs/agent-onboarding.md](docs/agent-onboarding.md), `skills/orient`, `skills/anti-slop`, `skills/pstack`, `skills/dr-eggbot`. Inventory: [docs/kit-inventory.md](docs/kit-inventory.md).

## Gap those projects leave

None of the above give you, together:

1. **Claim leases** that expire (issues are not claims)
2. **Workers never merge `main` or `dev`** as a hard rule, including cloud agents. Preview/nightly automerge is channel policy, not a worker.
3. **Revision-bound evidence receipts** (RED/GREEN/sabotage + exact head)
4. **Harness-neutral** TDD/mutation *setup* — detect stack at runtime, do not dump bun scripts into a Python repo
5. **KEEP/DISCARD** learning that feeds the roadmap without a second scheduler

That is this repository.
