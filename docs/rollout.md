# Rollout schemes

This is **not a second loop**. [SPEC.md](../SPEC.md) still owns claims, receipts, and merge authority for `dev` and `main`. `.verified-oss-loop/rollout.yml` only chooses **how fast** work rolls toward those gates.

Default is **Arch-style rolling** (bleeding edge). Set `scheme: staged` or `scheme: stable` for slower repos. Credit: [Arch Linux](https://wiki.archlinux.org/title/Arch_Linux) rolling release — we take the *pace*, not a worker merge of `main`.

```yaml
schema: verified-oss-loop.rollout.v1
scheme: rolling   # rolling | staged | stable
```

`oss-onboard --scheme staged` writes that value. Re-runs do not overwrite a locally edited rollout.yml (inventory `modified` / `local`).

## Channels

| Branch | Role |
|---|---|
| **preview** | Integration of feature branches. Operator tests here before promoting to nightly. |
| **nightly** | Overnight AI and cutting-edge. Accepts most changes under `rolling`. |
| **dev** | Gated integration. Human or required checks. Workers never merge. |
| **main** | Default / production. Maintainer merge only. Never force-push. |

Ladder:

```text
feature branch
  → preview   (automerge on rolling and staged)
  → nightly   (operator promote; overnight AI may PR here)
  → dev       (gated)
  → main      (gated)
```

## Schemes

| | `rolling` (default) | `staged` | `stable` |
|---|---|---|---|
| Worker base | `nightly` | `nightly` | `main` |
| Feature PR target | `preview` | `preview` | `main` |
| Overnight AI target | `nightly` | `nightly` | `main` |
| Automerge → preview | yes | yes | no |
| Automerge → nightly | yes (after checks) | no | no |
| Automerge → dev/main | **never** | no | no |

Arch-style: keep `rolling`. Feature PRs land on preview so you can try them; overnight runs land on nightly; you promote preview → nightly when preview looks right (`workflow_dispatch` on `promote-preview.yml`). `dev` and `main` stay human-gated.

`stable` is classic OSS: one default branch, PRs, humans merge. Use it for libraries that must not roll.

## Worker rules

1. `python3 .verified-oss-loop/rollout.py show`
2. Branch from `worker_base`. Open the PR at `feature_target` (day pass) or `overnight_target` (unattended overnight).
3. Fill the evidence receipt. Bind `head_revision`.
4. **Never merge `main` or `dev`.** Preview/nightly automerge is the authorized path for those channels, configured by this file, not a worker merge key for production.

## Maintainer settings

- Protect `main` and `dev`: PR required, no force-push, required smoke/receipt.
- `preview` and `nightly`: no required CODEOWNERS. Optional smoke. Automerge workflows need `contents: write` on the default `GITHUB_TOKEN` for same-repo PRs only (not forks).
- Create the extra branches once: `bash scripts/ensure-rollout-branches.sh --root . --push`

## What `--with-automation` copies

- `.github/workflows/automerge-preview.yml`
- `.github/workflows/automerge-nightly.yml`
- `.github/workflows/promote-preview.yml` (manual preview → nightly)

They no-op when `rollout.yml` forbids that channel. Fork PRs are never auto-merged.
