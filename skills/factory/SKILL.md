# Factory

Use the Verified OSS Loop to improve repos that opted into this standard. Do not invent a second loop.

## Do

1. Read this kit's `HITL.md`, `SPEC.md`, and `docs/factory.md`. Do not invent a third process.
2. If the target is `kvnloo/*` and opted in: `./bin/oss-onboard DIR --with-automation`. Mature forks that already have `AGENTS.md`: `./bin/oss-onboard DIR --layout mature` (kit under `.verified-oss-loop/`; never replace `AGENTS.md` or dump kit skills over `source: local`). Cluster similar issues from a **local** fixture (`scripts/cluster-similar-issues.py`, cap 64) — do not scrape trackers.
3. If the target is origin OSS: follow origin CONTRIBUTING. Do not copy labels or workflows there.
4. Claim **one** item. Isolated branch. Orient, then fail-then-pass, then shrink (`skills/orient`, `skills/tdd`, `skills/anti-slop`). Fill the evidence receipt.
5. Independent review (human or a review bot the project already runs). **Never merge `main` or `dev`.** Fork PRs stay on the fork until a human moves Linear to **Maintainer Review**. Then `scripts/publish-origin-from-hitl.py` opens the GitHub parent PR (`hitl-maintainer-review`). Non-fork plugin repos fail closed. The publisher never merges.

## Stop

- Linear is not Todo (origin writes).
- A competing PR or maintainer branch covers the scope.
- You would install Greptile/Codecov/CodSpeed secrets into a repo that did not ask.
- You were about to dump bun/pytest/cargo into the wrong stack.
- You were about to run `gitnexus analyze`, vendor GitNexus, or dump the pstack plugin tree.

## Pointers

- Loop: `SPEC.md`
- Bot catalog: `docs/quality-bots.md`
- Quality at volume: `docs/quality-at-scale.md`
- Graph/LSP onboarding: `docs/agent-onboarding.md`
- Inventory: `docs/kit-inventory.md`
- Rollout: `docs/rollout.md`
- HITL map: `HITL.md` (adapter: `docs/factory.md`)
