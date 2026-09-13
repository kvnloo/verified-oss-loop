# CI/CD hygiene

This is **not a second loop**. [SPEC.md](../SPEC.md) still owns claims, receipts, and merge of `main`/`dev`. This file is what long harness runs (Hermes-style isolated tests, one-shot coding CLIs such as [oh-my-pi / `omp`](https://omp.sh/)) taught about keeping **this kit's** Actions graph small and honest.

## Biggest findings

1. **Receipt CI must read the live PR body.** Binding evidence to `head_revision` is the point. The `pull_request` event payload can still hold the previous body after `git push`, so a check fails on a SHA the author already named in a later edit. Fetch `GET /repos/{owner}/{repo}/pulls/{n}` in the job. Put `head_revision` in the body **before** the push when you can; the live fetch still saves the rollup when you cannot.
2. **Cancel superseded runs.** `concurrency` + `cancel-in-progress: true` on receipt (per PR number) and smoke (per ref). Lingering red checks from an old SHA are how GitHub still looks broken after a green retry.
3. **Isolate the harness.** Kit proof is `bash tests/smoke.sh` in a temp dir. Do not talk to GitHub from that script. Do not inherit developer secrets, `~/.config`, or another repo's `.env`. Hermes pins a hermetic env and runs files in fresh processes so cross-test leakage cannot become a flake CI never sees. `omp` is a one-shot coding pass: doctor the environment, do the job, return text — it is not a merge bot and not a second SPEC.
4. **Stack-neutral Actions.** Dependabot here is Actions-only. Language lockfile updaters and four overlapping review comment bots are noise (lkml / Dependabot lesson). Catalog bots in [quality-bots.md](quality-bots.md); do not copy them into every target.
5. **Workflow files are inert until they exist on the default branch.** `workflow_dispatch` (promote-preview, label create) does not appear in Actions until merged to `main`. Feature-branch YAML is for review, not a live timer.
6. **Git channels ≠ URL paths.** `preview` / `nightly` as branch names must not become `/preview/preview/`. [rollout.md](rollout.md) Pages map.
7. **Workers never `git push origin main|dev`.** Automerge is channel policy on `preview`/`nightly` only, and never for forks. Required checks stay cheap: smoke + receipt. Mutation/`n/a` stays project policy.

## Community speed without spray

Unlabeled issues never enter the overnight Work branch. New GitHub issue forms apply `needs-discussion`. Maintainers (or Linear Todo) add `claimable`. Overnight triage comments on the newest discussion issue; it must not self-apply `claimable`. That is how queues clear: **discussion → one claimable leaf → one PR with a receipt**, not a spray of consolation PRs.

Higher-quality PRs: one issue, one `head_revision`, CODEOWNERS ping on protocol paths, receipt-before-review ([bedevere](https://github.com/python/bedevere)-shaped completeness, not a merge FSM). Independent review bots are SPEC §5, not §6.

## What we still skip

- Vendor Hermes `run_tests.sh`, pytest-xdist, or `omp` into onboard targets.
- A second scheduler, issue tracker, or “agent merge queue.”
- Required CODEOWNERS on `preview`/`nightly` (those channels exist to absorb chaos).
