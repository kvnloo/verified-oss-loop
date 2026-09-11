# Prior art

This protocol is a **contribution contract**. It is not a new issue tracker, CI product, or app generator. Credit the work we adapt.

Canonical short list: [REFERENCES.md](../REFERENCES.md).

## Pre-AI community health

| Name | URL | Reuse | Skip |
|---|---|---|---|
| GitHub Open Source Guides | https://opensource.guide/ | COMMUNITY, support links | ceremony for tiny specs |
| github/gitignore | https://github.com/github/gitignore | language gitignores | not a contribution loop |
| choosealicense.com | https://choosealicense.com/ | keep the project's existing LICENSE | do not overwrite |
| Contributor Covenant | https://www.contributor-covenant.org/ | optional CODE_OF_CONDUCT | not a claim lease |
| standard-readme | https://github.com/RichardLitt/standard-readme | README sections | not agent-native |
| cookiecutter | https://github.com/cookiecutter/cookiecutter | “generate then customize” | generates *apps*, not contribution policy |
| copier | https://github.com/copier-org/copier | updateable templates | same: app/project skeleton |
| cargo-generate | https://github.com/cargo-generate/cargo-generate | Rust crate templates | Rust-only |
| joelparkerhenderson/github-templates | https://github.com/joelparkerhenderson/github-templates | issue/PR wording | pre-AI; no evidence receipts |
| dwyl/repo-badges | https://github.com/dwyl/repo-badges | status badges | not a loop |
| TODO Group Repolinter | https://github.com/todogroup/repolinter | lint community files | policy lint, not claims |
| OpenSSF Scorecard | https://github.com/ossf/scorecard | security health | already in README |
| All Contributors | https://allcontributors.org/ | credit bots + humans | optional |
| DCO / CLA-assistant | https://developercertificate.org/ · https://github.com/cla-assistant/cla-assistant | identity of commits | project policy wins |
| issue-spec | https://github.com/higress-group/issue-spec | proposal → design → impl DAG | not a lease |
| CDEvents | https://github.com/cdevents/spec | delivery events | not a claim |
| Conventional Commits | https://www.conventionalcommits.org/ | optional | not required |
| semantic-release / release-please / changesets | https://github.com/semantic-release/semantic-release · https://github.com/googleapis/release-please · https://github.com/changesets/changesets | release automation | not contribution authority |
| pre-commit / commitlint | https://pre-commit.com/ · https://github.com/conventional-changelog/commitlint | local hooks | optional |
| JoshuaKGoldberg/create-typescript-app | https://github.com/JoshuaKGoldberg/create-typescript-app | modern TS community files + CI | TypeScript app generator |
| rust-cli/template | https://github.com/rust-cli/template | Rust CLI layout | not the loop |
| projen | https://github.com/projen/projen | synthesized project files | owns too much of the tree |

## AI-native instruction files

| Name | URL | Reuse |
|---|---|---|
| AGENTS.md | https://agents.md/ | root `AGENTS.md` is the portable agent file (Codex, Amp, Jules, Cursor, …) |
| CLAUDE.md / GEMINI.md / `.github/copilot-instructions.md` | Anthropic / Google / GitHub Copilot | aliases; prefer one AGENTS.md over N copies |
| aider CONVENTIONS.md | https://aider.chat/ | coding conventions; not a claim lease |
| Aperant self-development loop | https://github.com/AndyMik90/Aperant/discussions/306 | origin of this protocol |

## Verification tools (selected at runtime)

| Stack | Unit | Mutation | Note |
|---|---|---|---|
| Python | pytest | [mutmut](https://github.com/boxed/mutmut), cosmic-ray | score is project policy |
| JS/TS (bun) | `bun test` | project `mutate.ts` or Stryker | Dash-specific mutate.ts is *not* copied |
| JS/TS (node) | npm test / vitest / jest | [Stryker](https://stryker-mutator.io/) | if-present |
| Rust | `cargo test` | [cargo-mutants](https://github.com/sourcefrog/cargo-mutants) | |
| Go | `go test ./...` | n/a by default | do not fake a score |

## Quality-bot mesh (adapt; bots never become workers-who-merge)

| Name | URL | Reuse | Skip |
|---|---|---|---|
| LiteLLM PR bot mesh | https://github.com/BerriAI/litellm/pull/40744 | Greptile confidence + CodSpeed + Codecov on the exact head | requiring 4/5 to merge; dumping their Actions tree |
| kubernetes Prow + Tide | https://docs.prow.k8s.io/docs/components/core/tide/ | OWNERS, reviewer assignment, label merge *criteria* | Tide as a coding-agent merge bot |
| rust-lang/triagebot | https://github.com/rust-lang/triagebot | `/claim`-like commands, labels, nominate | bors keys for unattended workers |
| python/bedevere | https://github.com/python/bedevere | NEWS/issue/CLA completeness gates | language-specific NEWS as a global rule |
| home-assistant hassfest | https://developers.home-assistant.io/ | integration CI + codeowner ping | HA-specific integration layout |
| OpenSSF Scorecard Action | https://github.com/ossf/scorecard-action | weekly SARIF, branch protection | treating 10/10 as KEEP |
| CodeQL / Semgrep / OSV / zizmor | GitHub Advanced Security · semgrep · osv.dev · zizmorcore/zizmor | security_checks[] on the receipt | silent SARIF that nobody reads |
| Dependabot | https://github.com/dependabot/dependabot-core | Actions ecosystem only in this kit | npm/pip/cargo ecosystems on a spec repo |
| Greptile / CodeRabbit / Bugbot | greptile.com · coderabbit.ai · cursor.com | one independent reviewer | four overlapping comment bots |
| GitHub merge queue | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue | `merge_group` CI when the project enables a queue | queue merge as worker authority |
| Arch Linux rolling release | https://wiki.archlinux.org/title/Arch_Linux | bleeding-edge default channel (`rolling`) | worker merge of `main`; one scheme for every repo |

Factory HITL mapping: [factory.md](factory.md). Copied vs catalog: [quality-bots.md](quality-bots.md). Channel speed: [rollout.md](rollout.md).

## Agentic onboarding tools (orient; do not vendor)

| Name | URL | Reuse | Skip |
|---|---|---|---|
| GitNexus | https://github.com/abhigyanpatwari/GitNexus | MCP `query`/`context`/`impact` when already installed | `npx gitnexus analyze` from onboard; vendoring PolyForm Noncommercial source; generated `CLAUDE.md` |
| Serena | https://github.com/oraios/serena | MIT LSP symbol MCP as fallback | Installing it into every target |
| Context7 | https://github.com/upstash/context7 | Library docs at a pinned version | Treating it as this repo’s graph |
| DeepWiki | Cognition hosted wiki | First-hour orientation | Wiki as `tests.green` |
| repomix / gitingest | https://github.com/yamadashy/repomix · https://github.com/cyclotruc/gitingest | One packed snapshot | Repeating the pack instead of targeted reads |
| ast-grep | https://github.com/ast-grep/ast-grep | Structural search | Drive-by refactors found by glob |
| Aider repo map | https://github.com/Aider-AI/aider | Token-bounded local map | Aider as the claim lease |
| agents.md | https://agents.md/ | One `AGENTS.md` | Duplicate instruction files |
| pstack | https://github.com/cursor/plugins/tree/main/pstack | Use plugin if present; pointer skill | Copying 100+ Cursor playbooks; merge-the-PR playbooks for workers |
| Dr Eggbot | https://x.ai/bot/marketplace/bots/dr-eggbot-v2 | One-job skill/bot design | Vendoring the marketplace bot; assuming it lives in oss-factory |

Copied skills (original Apache-2.0 text, not plugin dumps): `skills/orient`, `skills/anti-slop`, `skills/pstack`, `skills/dr-eggbot`. Catalog: [agent-onboarding.md](agent-onboarding.md). Sync: [kit-inventory.md](kit-inventory.md).

## What still does not exist (this repo)

A stack-detecting **onboarding script** that writes the contribution contract (labels, claim lease, evidence PR, AGENTS.md, workers-never-merge) without generating an application. Cookiecutter/copier/create-typescript-app generate *codebases*. Scorecard lints *security*. issue-spec models *issue DAGs*. None of them bind AI work to a revision-bound receipt and a human merge gate.
