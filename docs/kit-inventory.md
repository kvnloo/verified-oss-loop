# Kit inventory and sync

Child repos that already ran `oss-onboard` need to pick up **new** standard skills when this kit releases, without clobbering tools a developer added by hand.

This is onboard mechanics, not a second contribution loop. [SPEC.md](../SPEC.md) still owns claims, receipts, and merge of `main`/`dev`. Channel speed is [rollout.md](rollout.md).

## Where provenance lives

Each onboarded repo gets a git-tracked file:

```text
.verified-oss-loop/inventory.yml
```

Commit it. The git history of that file is the VCS for “where did this skill come from?”

| `source` | Meaning | Re-run `oss-onboard` |
|---|---|---|
| `kit` | Copied from this standard (templates in verified-oss-loop) | Update if the file still matches the last kit write |
| `modified` | Was kit; this repo edited it | Skip. `--force` overwrites with the kit file |
| `local` | Developer-owned (extra `skills/*/SKILL.md`, or marked local) | **Never** overwrite, including `--force` |

`kit_revision` is the git SHA of the kit that last synced. Compare it to this repo’s HEAD when you want to know how far behind a child is.

## Sync rules

1. Missing kit path → write (this is how a new `skills/orient` lands in an already-onboarded tree).
2. Kit path, dest hash equals the hash stored at last sync → write the new template (subst still runs).
3. Kit path, dest hash differs → `modified`, skip.
4. Path not in the kit list (extra skill, a full pstack plugin copy, GitNexus-generated `.claude/skills`, …) → `local`, skip.
5. `LICENSE` is still never overwritten and is not in the inventory.
6. `--force` refreshes `kit` and `modified` only.

First re-run after this inventory exists: existing kit paths that do not match the *current* template are `modified` (we cannot tell an old template from a local edit). New files still appear. To take the new standard for those paths: `--force`, or revert the file and sync again.

To keep a customized kit skill forever:

```bash
python3 scripts/kit-inventory.py mark --root /path/to/repo --path skills/tdd/SKILL.md --source local
```

(or the copy at `.verified-oss-loop/kit-inventory.py` in the child)

## Commands

```bash
./bin/oss-onboard /path/to/repo                  # sync
./bin/oss-onboard /path/to/repo --force           # kit+modified only
./bin/oss-onboard /path/to/repo --status          # print inventory
python3 scripts/kit-inventory.py show --root /path/to/repo
```

Factory: re-run onboard on opted-in `kvnloo/*` after a kit release. New kit skills (`pstack`, `dr-eggbot`, …) appear because they are missing dest files. Do not `--force` unless the child asked to take kit versions of edited files.
