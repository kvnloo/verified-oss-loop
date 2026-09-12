# Verified OSS Loop

A lightweight, project-neutral protocol for open-source communities that want humans and coding agents to improve a repository in parallel without duplicate work, unverifiable claims, or autonomous merge authority.

## The loop

```text
maintainer roadmap
→ prioritized issue queue
→ bounded claim lease
→ isolated branch/worktree
→ implementation + evidence receipt
→ independent verification
→ maintainer/human merge decision
→ outcome feeds the next roadmap revision
```

This grew from the [Community-wide Distributed Self-Development Loop](https://github.com/AndyMik90/Aperant/discussions/306), then informed [Hermes autoresearch](https://github.com/NousResearch/hermes-agent/issues/5114), [reversible harness refinement](https://github.com/NousResearch/hermes-agent/issues/93306), and household edge-compute proposals across agent runtimes.

## What it adds

Existing systems already cover important parts:

- GitHub Issues/Projects: backlog and roadmap
- [issue-spec](https://github.com/higress-group/issue-spec): proposal/design/implementation DAGs
- [CDEvents](https://github.com/cdevents/spec): delivery events
- [OpenSSF Scorecard](https://github.com/ossf/scorecard): repository security health

Verified OSS Loop adds the missing contribution contract:

- maintainer-owned priority and acceptance
- duplicate-safe claim leases
- isolated execution
- revision-bound evidence
- reproducible RED/GREEN/sabotage/build receipts
- independent review
- KEEP/DISCARD decisions
- explicit human merge authority
- cost/resource accounting without pay-to-win priority

## Principles

1. **Maintainers own direction.** Agents and contributors propose; they do not redefine the roadmap.
2. **Issues are not claims.** Work begins only after policy and duplicate checks.
3. **Claims expire.** Stale contributors cannot block an issue forever.
4. **Every result binds to a revision.** Tests from another head are not evidence.
5. **Tests are necessary, not sufficient.** Build/runtime/user-path proof follows project policy.
6. **Generation and verification are separate.** The implementer does not self-approve.
7. **Workers never merge `main` or `dev`.** Channel automerge (preview, and nightly under `rolling`) is maintainer-configured by `.verified-oss-loop/rollout.yml`, not a worker merge key.
8. **Failure is useful.** DISCARD receipts preserve why an approach failed.
9. **No ceremonial automation.** Small projects can adopt this with labels and a Markdown receipt.
10. **Project policy wins.** This protocol never overrides CONTRIBUTING, security, AI disclosure, CLA/DCO, or review rules.

## Use as boilerplate

This repo is the protocol (`SPEC.md`) plus an onboarding kit. It does not generate an application. Cookiecutter/copier generate *codebases*; this copies a contribution contract.

```bash
git clone https://github.com/kvnloo/verified-oss-loop
./bin/oss-onboard /path/to/repo --with-automation --scheme rolling
# Pages URL map (git preview ≠ /preview/): --with-pages
# slower: --scheme staged   classic: --scheme stable
# mature fork (keep AGENTS.md; kit under .verified-oss-loop/):
./bin/oss-onboard /path/to/repo --layout mature
python3 scripts/cluster-similar-issues.py tests/fixtures/issues-tiny.json
# or a new tree:
./scripts/init-oss-repo.sh --new ./my-lib --name my-lib --owner YOUR_LOGIN --git
```

What it does:

- Detects stack from the tree (`pyproject.toml`, `package.json`/`bun.lock`, `Cargo.toml`, `go.mod`).
- Writes `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, a paste-ready `prompt.md` that links to **that** repo, issue/PR templates, and kit skills (`autodevelop`, `orient`, `tdd`, `anti-slop`, `pstack`, `dr-eggbot`, `verify`) via [kit inventory](docs/kit-inventory.md). Re-runs update **kit** files; they never overwrite `source: local` skills (pstack plugin copies, hand-written tools).
- Pins the unit and mutation commands it saw. If mutation is `n/a`, the receipt says `n/a` — it does not invent a score.
- `--with-automation` adds stale/labeler, **receipt + exact-head**, claim-expiry, OpenSSF Scorecard, Actions-only Dependabot, CODEOWNERS, `create-labels.sh`, and **preview/nightly automerge + promote-preview** gated by `.verified-oss-loop/rollout.yml`. Default `--scheme rolling` (Arch-style). `--scheme staged` or `--scheme stable` for slower repos. [docs/rollout.md](docs/rollout.md). AI review / coverage / perf apps are catalogued in [docs/quality-bots.md](docs/quality-bots.md), not copied. Automation still does not merge `main`.
- `--with-pages` copies `scripts/pages-url-map.py`, `.verified-oss-loop/pages-url-map.yml`, and a paste snippet for the maintainer’s own Pages workflow. Git channels (`preview`, `nightly`) are not URL folders. Default map: `main` → `{base}`, `nightly` → `{base}nightly/`, `preview` → `{base}next/`, features → `{base}wip/<slug>/`. If the target already has `pages.yml` or `build-pages.py`, onboard prints the collision warning and runs `check` even without the flag. Does not invent a site generator. [docs/rollout.md](docs/rollout.md).
- `--layout mature`: kit under `.verified-oss-loop/` + `docs/verified-oss-loop.md`. Does **not** replace a mature `AGENTS.md` or dump kit skills over `source: local`. See [docs/verified-oss-loop.md](docs/verified-oss-loop.md).
- Similar-issue clustering: `scripts/cluster-similar-issues.py` + `tests/fixtures/issues-tiny.json` (8 issues, cap 64). No live tracker scrape.
- Does **not** run GitNexus, dump pstack, or rewrite `AGENTS.md` with a second H1. Graph/LSP/pstack/eggbot: [docs/agent-onboarding.md](docs/agent-onboarding.md).
- Factory HITL: [HITL.md](HITL.md) maps Linear Triage→…→Done onto this loop (`github_writes=0` until Todo; workers never merge; traction formula does not set claim priority). Adapter: [docs/factory.md](docs/factory.md).
- `--labels` creates GitHub labels when `gh` is authenticated.
- `--install` on `setup-verify.sh` is opt-in and only installs a mutator for the detected primary stack ([Stryker](https://github.com/stryker-mutator/stryker-js), [mutmut](https://github.com/boxed/mutmut), or [cargo-mutants](https://github.com/sourcefrog/cargo-mutants)). Go gets `go test` and an honest `n/a`.
- Never overwrites `LICENSE`. Never copies another project's UI, `.env`, or device tests.

See [scripts/init-oss-repo.sh](scripts/init-oss-repo.sh), [harnesses/stacks.json](harnesses/stacks.json), [REFERENCES.md](REFERENCES.md), [docs/prior-art.md](docs/prior-art.md), [docs/quality-bots.md](docs/quality-bots.md), [docs/quality-at-scale.md](docs/quality-at-scale.md), [docs/agent-onboarding.md](docs/agent-onboarding.md), [docs/kit-inventory.md](docs/kit-inventory.md), [docs/rollout.md](docs/rollout.md), [HITL.md](HITL.md), and [docs/factory.md](docs/factory.md).

Proof for this kit: `bash tests/smoke.sh`.

## Minimal adoption

A project needs only:

- roadmap or priority document
- issue labels: `priority`, `claimable`, `claimed`, `needs-review`, `blocked`
- claim comment with expiry
- evidence section in the PR template
- one independent reviewer (human or a review bot the project already runs — still not merge)
- human merge gate on `main` (and `dev` when those channels exist)

Default is bleeding-edge rolling (`preview` → `nightly` → gated `dev`/`main`). See [docs/rollout.md](docs/rollout.md).

See [SPEC.md](SPEC.md) for the complete contracts.

## Scope

This protocol applies to any open-source project. Distributed compute and household-device meshes are a separate optional execution layer for projects that can benefit from them.

## License

Apache-2.0
