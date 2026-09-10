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

## What still does not exist (this repo)

A stack-detecting **onboarding script** that writes the contribution contract (labels, claim lease, evidence PR, AGENTS.md, workers-never-merge) without generating an application. Cookiecutter/copier/create-typescript-app generate *codebases*. Scorecard lints *security*. issue-spec models *issue DAGs*. None of them bind AI work to a revision-bound receipt and a human merge gate.
