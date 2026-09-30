# Nightly: linux-next style integration

`nightly` is **the default branch plus every active feature branch listed in a manifest**. A job rebuilds it from scratch on a schedule, the way [linux-next](https://www.kernel.org/doc/man-pages/linux-next.html) is rebuilt from `Next/Trees` every day. It is disposable and force-pushed. Nothing is ever merged *from* nightly.

- **Default branch** (`main`, `master`, `trunk`): the minimal working core. Changes reach it only through reviewed PRs.
- **`nightly`**: default + `.nightly/branches`, regenerated automatically.
- **`dev` and `preview`** are retired. `automerge-preview.yml`, `automerge-nightly.yml` and `promote-preview.yml` are replaced by `nightly-rebuild.yml` (see [Retiring the ladder](#retiring-the-ladder)).

The rebuild never grants merge authority. "Merged and green in `nightly-20261001`" is evidence for a PR, not a merge. Graduation to the default branch stays one reviewed PR per branch ([SPEC.md](../SPEC.md), [HITL.md](../HITL.md)).

## Pieces

| file | role |
|---|---|
| `scripts/nightly-rebuild.sh` (installed as `.verified-oss-loop/nightly-rebuild.sh`) | the rebuild |
| `.nightly/branches` (template: `templates/.nightly/branches`) | the ordered manifest, on the default branch |
| `.github/workflows/nightly-rebuild.yml` (template) | daily schedule + `workflow_dispatch` |
| `docs/nightly-manifests/<repo>.branches` | starting manifests for the kvnloo repos, from the 2026-09-30 survey |
| `tests/nightly-rebuild.sh` | fixture test (run by `tests/smoke.sh`) |

## Manifest

```text
# branch                              mode      owner        note
feat/resource-posture-v0              required  claude-code  # stack tip
feat/claude-code-harness              required  claude-code
exp/bend-aodl-gate                    advisory  claude-code
```

- **Order matters.** Branches merge in file order, so an earlier entry wins a conflict. List a stack's **tip first**: its lower layers then report `CONTAINED` instead of cascading conflicts.
- `required` (default): the branch's tests must pass or it is dropped. `advisory`: it is merged even when its tests fail, and the failure is reported. Use it sparingly.
- `owner` is the worker tag (`claude-code`, `grok`, `muse`, `omp`, `hermes`, `cursor`, `codex`, `kevin`). It feeds the report only.
- Invalid mode, a bad branch name, a duplicate entry, or the default/target branch in the list is a manifest error: the job exits 2 and pushes nothing.
- Where it is read from, in order: `--manifest FILE`, `<default>:.nightly/branches`, then `nightly-manifest:.nightly/branches` (an unprotected fallback branch for repos whose ruleset makes a PR per manifest edit too heavy).
- Do not list dependabot branches (they go straight to default by PR) or ladder twins (`*-preview`, `*-nightly`, `master-local-*`, `reconcile/*`, `consolidate/*`).

## What one rebuild does

1. Fetch every branch. Find the default branch and the current `nightly` (the lease value).
2. Build in a throwaway `git worktree` at the default branch; your checkout is never touched. Run `NIGHTLY_TEST_CMD` on the bare default. **If the default is red, stop and push nothing**: nightly must never mask a broken core.
3. With `--rerere`, restore recorded conflict resolutions from the `nightly-rerere` branch.
4. For each manifest entry, in order:

   | outcome | meaning |
   |---|---|
   | `GONE` | the branch no longer exists; remove it from the manifest |
   | `GRADUATED` | already in the default branch; remove it from the manifest (the report lists these under **Manifest hygiene**) |
   | `CONTAINED` | an earlier entry (a stack tip, or a patch-equivalent copy) already carries it; keep it listed |
   | `DROPPED` conflict | merge conflict; the report lists the files and which earlier entries (or the default branch itself) touch them |
   | `DROPPED` tests | a `required` branch whose smoke failed after merging; it is backed out |
   | `WARN` | an `advisory` branch whose smoke failed; kept |
   | `MERGED` | merged (`--no-ff`, message `nightly: merge <branch> @ <sha>`) and green |

   `GRADUATED` means any of: the tip is an ancestor of the default (merge commit, fast-forward); merging it into the default yields the default's own tree (squash- or rebase-merged, patch-equivalent); or, with `gh`, a PR from that branch was merged with exactly this tip as its head (squash-merged, and the default has since moved on the same files). The `gh` check runs when `gh` is installed and the remote is on github.com; `NIGHTLY_GH=0` turns it off. A branch that gained commits after its PR merged is not graduated. `CONTAINED` is only ever about earlier manifest entries, never the default branch.

5. Run the full test on the final tree. A red final tree means branches that pass alone fail together. The job drops entries, last first, until the required-only tree is green, spending at most `--max-rebuilds` (5) extra test runs; the culprit is reported. Advisory entries may leave the final tree red (`final_gate: red-advisory`) only if the same tree without them is green.
6. Write `.nightly-out/report.json` (machine-readable, schema `verified-oss-loop.nightly-report.v1`) and `.nightly-out/REPORT.md` (step summary), plus per-run logs.
7. Push only when not a dry run: `git push --force-with-lease=refs/heads/nightly:<old>` then the dated tag `nightly-YYYYMMDD`; tags older than 30 days are pruned. **If the rebuilt tree equals the current nightly, nothing is pushed.** A lease rejection (someone moved nightly mid-run) fails the job.

Test results are cached by tree, so a tree is never tested twice. Merge commits use the `github-actions[bot]` identity and a fixed timestamp per run, so rebuilding the same list yields the same commits.

## Safety

- **Dry run is the default outside CI.** Locally, `scripts/nightly-rebuild.sh` builds, tests and reports, and leaves the result at the local ref `refs/nightly/candidate`. Pushing needs `CI=true` or an explicit `--push`. `--dry-run` / `--no-push` / `DRY_RUN=true` always win.
- The job writes only `refs/heads/nightly`, `refs/tags/nightly-*` and, with `--save-rerere`, `refs/heads/nightly-rerere`. It refuses a target equal to the default branch.
- It refuses to push without a test command unless `NIGHTLY_ALLOW_NO_TESTS=1`.
- `set -euo pipefail` throughout. Any unexpected failure exits non-zero before the push and still writes a report with `outcome: error`.
- Recommended ruleset (a maintainer decision): protect `nightly` against deletion and allow force-push only by the Actions bot. Keep the default-branch rulesets. Because those require linear history, nightly content reaches the default branch through squash or rebase PRs of the *feature branch*, never by merging nightly.

## Adopting it in a repo

1. Re-sync the kit: `bin/oss-onboard /path/to/repo --with-automation` (add `--layout mature` for mature repos). This installs `.verified-oss-loop/nightly-rebuild.sh`, `.github/workflows/nightly-rebuild.yml` and a commented `.nightly/branches`.
2. Fill `.nightly/branches`. For the kvnloo repos, start from `docs/nightly-manifests/<repo>.branches` in this kit; each file header carries that repo's test command.
3. Tune it locally before anything can push:

   ```bash
   NIGHTLY_TEST_CMD='python3 -m unittest discover -s tests' \
     .verified-oss-loop/nightly-rebuild.sh --dry-run --manifest .nightly/branches
   cat .nightly-out/REPORT.md
   ```

   Reorder or remove entries until the report says what you want.
4. Set the repository variable `NIGHTLY_TEST_CMD` (and optionally `NIGHTLY_SMOKE_CMD` for a faster per-branch check, `NIGHTLY_RERERE=true`). Settings → Secrets and variables → Actions → Variables.
5. Land the manifest and workflow on the default branch by PR.
6. Run it once by hand with **dry_run** checked (Actions → Nightly rebuild → Run workflow) and read the step summary. After that the schedule (08:17 UTC daily) takes over.
7. Tell contributors: *open PRs against the default branch; add your branch to `.nightly/branches` to ride nightly.*

### Conflict memory (optional)

When two listed branches conflict and a human resolves it once (`git merge` with `rerere.enabled=true`, then commit), push the resolution to `nightly-rerere` by running a push-mode rebuild with `--rerere --save-rerere`, or set `NIGHTLY_RERERE=true` in CI. Later rebuilds replay it. A replayed resolution is still tested; its entry is reported as `conflict resolved by rerere`.

## Retiring the ladder

The old ladder was `feature → preview → nightly → dev → main`, driven by `automerge-preview.yml`, `automerge-nightly.yml` and `promote-preview.yml`. In practice `dev`/`preview` carried no unique content (see the 2026-09-30 survey), and the promote workflows either never ran or failed with `empty ident name`. The rebuild folds in the fixes from `arch/promotion-hardening` (bot identity, `set -euo pipefail`, skip when there is nothing to publish, the `.verified-oss-loop/` path that exists in both layouts), so that branch does not need to merge first.

Per repo, in this order:

1. **Retarget open PRs** whose base is `preview`, `dev` or a legacy branch to the default branch (`gh pr edit <n> --base <default>`). GitHub closes a PR when its base branch is deleted.
2. **Preserve unique content.** For each of `dev`, `preview` and the old `nightly`, check `git diff --quiet $(git merge-base origin/<default> origin/<b>) origin/<b>`. Anything with real content lives on (or is moved to) a feature branch that goes into `.nightly/branches`. Push an archive tag first when in doubt: `git push origin <sha>:refs/tags/archive/<repo>-<b>-<date>`.
3. **Remove the workflows** in the same PR that adds `nightly-rebuild.yml`: delete `.github/workflows/automerge-preview.yml`, `automerge-nightly.yml` and `promote-preview.yml`. (Re-running `oss-onboard` still copies them until the kit drops them; delete them after the sync, or mark them `local` in the inventory.)
4. **Update contributor docs**: "open PRs against the default branch; add your branch to `.nightly/branches` to ride nightly."
5. **Let the first rebuild replace `nightly`.** The first push-mode run force-pushes it with a lease on its current SHA.
6. **Delete `dev` and `preview`** once no open PR targets them: `git push origin --delete dev preview`.
7. **Switch `.verified-oss-loop/rollout.yml` to `scheme: stable`.** Under this model workers branch from the default branch and open PRs against it, and no channel automerges, which is exactly `stable` (it names the default `main`; read it as `master`/`trunk` where that applies). Nightly integration is the rebuild's job, not a scheme's.
