## Summary

Fixture PR with a complete evidence receipt.

## Evidence

```yaml
issue: 42
base_revision: abcdef1
head_revision: 1234567890abcdef1234567890abcdef12345678
tests:
  red: bash tests/smoke.sh # expected fail on missing receipt keys
  green: bash tests/smoke.sh
  sabotage: break check-receipt.py required key; expect fail
mutation: n/a — this repo is shell templates; smoke.sh is the unit check
runtime_evidence: []
limitations: []
ai_assistance: unattended
```
