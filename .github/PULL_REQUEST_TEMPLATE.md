## Summary

<!-- What this PR changes, in one paragraph. -->

## Checklist

- [ ] **Searched issues/PRs**: no duplicate of an open claim or existing PR
- [ ] **One leaf**: linked `claimable` issue (not an unlabeled or `needs-discussion` ticket unless a human assigned it)
- [ ] **Claimed issue**: work started after a bounded claim, not from the issue title alone
- [ ] **Receipt SHA**: `head_revision` is this PR's SHA (set it in the body before push when you can)
- [ ] **Fail-then-pass**: bug fixes include red then green (command + expected result)
- [ ] **No secrets**: no tokens, pairing codes, `.env`, or API keys
- [ ] **Mode** (select one):
  - [ ] **Unattended** — donated compute (cloud agent, autonomous run)
  - [ ] **Copilot** — human reviewed the diff before this PR
- [ ] **Workers never merge `main`/`dev`**: this PR does not grant worker merge of production

## Changes

-

## Testing

```bash
bash tests/smoke.sh
```

## Evidence

```yaml
issue:
base_revision:
head_revision:
tests:
  red:
  green:
  sabotage:
mutation: n/a — this repo is shell templates; smoke.sh is the unit check
runtime_evidence: []
limitations: []
ai_assistance:
```

CI fetches the live PR body and runs `scripts/check-receipt.py` against this block and the PR head SHA. Independent review bots are not merge.

## Related

<!-- Fixes #123 -->
