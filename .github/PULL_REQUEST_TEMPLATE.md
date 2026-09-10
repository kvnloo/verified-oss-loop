## Summary

<!-- What this PR changes, in one paragraph. -->

## Checklist

- [ ] **Searched issues/PRs**: no duplicate of an open claim or existing PR
- [ ] **Claimed issue**: work started after a bounded claim, not from the issue title alone
- [ ] **Fail-then-pass**: bug fixes include red then green (command + expected result)
- [ ] **No secrets**: no tokens, pairing codes, `.env`, or API keys
- [ ] **Mode** (select one):
  - [ ] **Unattended** — donated compute (cloud agent, autonomous run)
  - [ ] **Copilot** — human reviewed the diff before this PR
- [ ] **Workers never merge**: this PR waits for a human maintainer

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

## Related

<!-- Fixes #123 -->
